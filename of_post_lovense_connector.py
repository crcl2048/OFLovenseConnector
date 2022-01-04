# Copyright (C) 2021 crcl2048
# This program is free software; you can redistribute it and/or modify it under the terms of the 
# GNU General Public License as published by the Free Software Foundation; version 2.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without 
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this program; 
# if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

import requests
import json
import time
import re
import urllib
import urllib3
import ssl

# Basic command class, supporst default 'action' types, as well as patterns
# The lovense documentation is, uh, not great: https://www.lovense.com/sextoys/developer/doc
# YMMV if trying to modify this to do something else, the docs have a couple of examples (patterns, presets, and actions), but it's unclear
# outside of the examples how the API is formed.
class LovenseCommand:
    def __init__(self, action, time, command = "Function", patternSequenceTime = None, strength = None):
        self.apiVer = 1 # per the docs, always 1
        self.command = command # can be 'Function' or 'Preset' or something else (lets be honest, the lovense docs are veeeeeeery bad.)

        if action is not None:
            self.action = action # vibrate, pulse, etc

        self.timeSec = time # in seconds
        # not included: toy (no idea how to even get the IDs, isn't covered in the docs, so this is all for one!)
        #               loopRunningSec, loopPauseSec -- may be needed, we will see.

        # Pattern Support
        if patternSequenceTime is not None:
             # Always V:1 (Version)
             # F:v (Features, vibrate -- other toys have other features, not included here, see the docs above)
             # S: - start of the sequence timing.
            self.rule = "V:1;F:v;S:" + str(patternSequenceTime) + "#"

        # Strengths expected by the API in string form of S1;S2;S3, convert the array here.
        if strength is not None:
            strengthStr = ""
            for s in strength:
                strengthStr += str(s) + ";"
            self.strength = strengthStr[:strengthStr.__len__() - 1] # drop the trailing ;, unsure if it makes a difference


    # dirty serialization to JSON to pass the command to the toy
    def toJSON(self):
        return self.__dict__

    # todo - may need more here, will see.

# a basic connection for a lovense device, can send LovenseCommand objects 
class LovenseConnection:
    def __init__(self, url, port):
        self.__url = url
        self.__port = port
        self.__headers = {'Content-type': 'application/json'}
        urllib3.disable_warnings() # who would have thought this sex toy would have issues with its SSL certificate, color me shocked.

    def ProcessCommand(self, cmd):
        # print(cmd.__dict__)
        url = "https://" + self.__url + ":" + str(self.__port) + "/command"

        resp = requests.post(url, json=cmd.__dict__, headers=self.__headers, verify=ssl.CERT_NONE)
        # just print the response for now
        # print(resp.text)

        # sleep for the duration of the command (unless the default pattern, this prevents commands from overlapping, but does block the thread).
        if cmd.timeSec < 1000:
            time.sleep(cmd.timeSec)

    def TestConnection(self):
        print("Testing the connection. You should feel a low vibration for 3 seconds")
        self.ProcessCommand(LovenseCommand("Vibrate:1", 3))

    def __del__(self):
        # when deleted, send a stop command
        self.ProcessCommand(LovenseCommand("stop", 1))

# Monitors a OF newsfeed post, at a rate of 1 update/20s checking for new likes / comments
# Future idea: can this be connected to the push notifications? (looks like there is a push-reciever library for python)
# but not everyone has those enabled, so it may not be universally useful.
class PilloryWatcher:

    __DefaultVibration = LovenseCommand("Vibrate:1", 86400)
            # Vibrate at low intensity (this is replaced by comments and likes when they come in).
            # but is otherwise always active to ensure that the sub remains engaged :)
            # Obivously once the feed being monitored stops being updated (e.g., pillory ended)
            # you will want to manually stop the toy (closing this program will send a stop command when the connector destructs)
    
    def __init__(self, postLink, connection):
        
        self.__post = postLink
        self.__connection = connection

        self.__initial_likes, self.__initial_comments = self.__ReadPilloryLikesAndComments()
    def __ReadPilloryLikesAndComments(self):
        response = urllib.request.urlopen(self.__post)
        text = response.read().decode("UTF-8")
        # this is such a nasty hack. a proper api would be nice, but doesn't exist (or more likely is not public facing, so this script will break if the underlying HTML changes, which is bad)
        # but also, this is for fun and not meant as production ready code in an IEC 61508 safety system. 
        match = re.search("likes\":(\d+),\"comments\":(\d+)", text, re.IGNORECASE)
        return int(match.group(1)), int(match.group(2))

    # being honest, there probably should be some sort of way to kill this, but folks can probably just click the 'x' in the top corner.
    def Process(self, skipInitial = False):
        # Start the low level, background buzzing (this runs at all times during the main loop)
        self.__connection.ProcessCommand(self.__DefaultVibration)

        # Wait 5 seconds before starting
        time.sleep(5)

        self.__lastLikes = self.__initial_likes
        self.__lastComments = self.__initial_comments

        if skipInitial is False:
            self.__ProcessInitials()

        ## main loop
        while True:
            time.sleep(20) # update each 20 seconds when not processing commands

            # Read updated likes and comments
            newLikes, newComments = self.__ReadPilloryLikesAndComments()

            # Process new likes
            likesDiff = newLikes - self.__lastLikes
            if likesDiff > 0:
                print(str(likesDiff) + " new likes!")
                self.__lastLikes = newLikes # save for next time
                while likesDiff > 0:
                    self.__VibrateLike()
                    time.sleep(2)
                    likesDiff -= 1
            
            # Process new comments
            commentsDiff = newComments - self.__lastComments
            if commentsDiff > 0:
                print(str(commentsDiff) + " new comments!")
                self.__lastComments = newComments # save for next time
                while commentsDiff > 0:
                    self.__VibrateComment()
                    time.sleep(2)
                    commentsDiff -= 1

    def __ProcessInitials(self):
        # Process the initial likes
        print("Processing " + str(self.__initial_likes) + " initial likes!")
        while self.__initial_likes > 0:
            self.__VibrateLike()
            time.sleep(2)
            self.__initial_likes -= 1

        print("Processing " + str(self.__initial_comments) + " initial comments!")
        # Process the initial comments
        while self.__initial_comments > 0:
            self.__VibrateComment()
            time.sleep(2)
            self.__initial_comments -= 1

    def __VibrateLike(self):
        print("Processing like!")
        # for likes, a 6 second vibration between high, medium, low, alternating every 1000ms
        likeCmd = LovenseCommand(None, 6, "Pattern", 1000, [20, 10, 1])
        self.__connection.ProcessCommand(likeCmd)
        # restore the default
        self.__DefaultVibrate()
         

    def __VibrateComment(self):
        print("Processing comment!")
        # for comments, 8 seconds, 500ms switching time, high to low.
        commentVibrate = LovenseCommand(None, 8, "Pattern", 500, [20, 1])
        self.__connection.ProcessCommand(commentVibrate)
        # return to default before leaving
        self.__DefaultVibrate()

    def __DefaultVibrate(self):
        self.__connection.ProcessCommand(self.__DefaultVibration)


def main():
    print("OF Pillory / Lovense Connector!")
    print("This script will monitor a newsfeed post on OF (for example, a pillory), and engage a connected Lovense toy when new likes or comments are detected.")
    permission = input("This script will engage connected Lovense toys. Confirm that you have permission to do so (if permission is required). Type 'YES' to continue: ")
    if permission.lower() != "yes":
        return 0

    toyURL = input("Enable 'Game Mode' in the settings of the Lovense Remote app, and enter the 'Local IP' here: ")
    while bool(re.match("^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", toyURL)) is False:
        toyURL = input("Invalid IP address. Try again: ")

    toyPort = input("Enter the 'Https Port' here: ")
    while toyPort.isnumeric() is False: # isnumeric disallows floating point, so that is good :)
        toyPort = input("Invalid Port. Try again: ")

    # Create our connector
    toyConnection = LovenseConnection(toyURL, toyPort)
    toyConnection.TestConnection()

    pilloryID = input("Please provide the pillory post link (click on the share link on the post, and paste that here): ")
    # connect to the newsfeed post
    watcher = PilloryWatcher(pilloryID, toyConnection)
    # this blocks
    # You can change the parameter 'skipInitial' to 'True' here to skip processing of existing likes/comments on the post
    # only new likes/comments would be processed.
    watcher.Process(False)

if __name__ == "__main__":
    main()
