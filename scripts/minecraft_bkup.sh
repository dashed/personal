#!/usr/bin/env bash
#
# adapted from:
# https://github.com/benjick/Minecraft-Autobackup/blob/master/minecraft_autobackup.sh

#Variables

# DateTime stamp format that is used in the tar file names.
STAMP=$(date +%m-%d-%Y_%H.%M.%S)

# The screen session name, this is so the script knows where to send the save-all command (for autosave)
SCREENNAME="minecraft"

# Whether the script should tell your server to save before backup (requires the server to be running in a screen $
AUTOSAVE=1

# Notify the server when a backup is completed.
NOTIFY=1

# Backups DIR name (NOT FILE PATH)
BACKUPDIR="backups"

# temp folder to copy contents to
TEMPDIR="temp"

# absolute path to minecraft folder
MC_DIR="/root/minecraft/"

# MineCraft server properties file name
PROPFILE="server.properties"

# Enable/Disable (0/1) Automatic CronJob Manager
CRONJOB=1

# Update every 'n' Minutes
UPDATEMINS=60

# Delete backups older than 'n' DAYS
OLDBACKUPS=7

# Enable/Disable Logging (This will just echo each stage the script reaches, for debugging purposes)
LOGIT=1

# *-------------------------* SCRIPT *-------------------------*
# Set todays backup dir

if [ $LOGIT -eq 1 ]
then
   echo "$(date +"%G-%m-%d %H:%M:%S") [LOG] Starting Justins AutoBackup Script.."
   echo "$(date +"%G-%m-%d %H:%M:%S") [LOG] Working in directory: $PWD."
fi

BACKUPDATE=$(date +%m-%d-%Y)
FINALDIR="$BACKUPDIR/$BACKUPDATE"

if [ $LOGIT -eq 1 ]
then
   echo "$(date +"%G-%m-%d %H:%M:%S") [LOG] Checking if backup folders exist, if not then create them."
fi

if [ -d $TEMPDIR ]
then
   echo -n < /dev/null
else
   mkdir "$TEMPDIR"

   if [ $LOGIT -eq 1 ]
   then
      echo "$(date +"%G-%m-%d %H:%M:%S") [LOG] Created Folder: $TEMPDIR"
   fi

fi

if [ -d $BACKUPDIR ]
then
   echo -n < /dev/null
else
   mkdir "$BACKUPDIR"

   if [ $LOGIT -eq 1 ]
   then
      echo "$(date +"%G-%m-%d %H:%M:%S") [LOG] Created Folder: $BACKUPDIR"
   fi

fi

if [ -d "$FINALDIR" ]
then
   echo -n < /dev/null
else
   mkdir "$FINALDIR"

   if [ $LOGIT -eq 1 ]
   then
      echo "$(date +"%G-%m-%d %H:%M:%S") [LOG] Created Folder: $FINALDIR"
   fi

fi

if [ $OLDBACKUPS -lt 0 ]
then
   OLDBACKUPS=3
fi

# Deletes backups that are 'n' days old
if [ $LOGIT -eq 1 ]
then
   echo "$(date +"%G-%m-%d %H:%M:%S") [LOG] Removing backups older than $OLDBACKUPS days."
fi
find "$PWD/$BACKUPDIR" -type d -mtime +"$OLDBACKUPS" | grep -v -x "$PWD/$BACKUPDIR" | xargs rm -rf


# --Check for dependencies--

#Is this system Linux?
#LOL just kidding, at least it better be...

#Get level-name
if [ $LOGIT -eq 1 ]
then
   echo "$(date +"%G-%m-%d %H:%M:%S") [LOG] Fetching Level Name.."
fi

while read line
do
   VARI=$(echo "$line" | cut -d= -f1)
   if [ "$VARI" == "level-name" ]
   then
      WORLD=$(echo "$line" | cut -d= -f2)
   fi
done < "$MC_DIR/$PROPFILE"

if [ $LOGIT -eq 1 ]
then
   echo "$(date +"%G-%m-%d %H:%M:%S") [LOG] Level-Name is $WORLD"
fi

rsync -av --exclude='logs' --exclude='minecraft_server*' "$MC_DIR/" "$TEMPDIR"

BFILE="$STAMP.tar.gz"
BKUP_CMD="tar -czf $FINALDIR/$BFILE $TEMPDIR"

if [ $LOGIT -eq 1 ]
then
   echo "$(date +"%G-%m-%d %H:%M:%S") [LOG] Packing and compressing minecraft to tar file: $FINALDIR/$BFILE"
fi

if [ $NOTIFY -eq 1 ]
then
   screen -x $SCREENNAME -X stuff "$(printf "say Backing up minecraft.\r")"
fi

#Create timedated backup and create the backup directory if need.

# Run backup command
screen -x $SCREENNAME -X stuff "$(printf "\rsave-off\r")"
$BKUP_CMD
screen -x $SCREENNAME -X stuff "$(printf "\rsave-on\r")"

if [ $NOTIFY -eq 1 ]
then
   # Tell server the backup was completed.
   screen -x $SCREENNAME -X stuff "$(printf "say Backup Completed.\r")"
fi

if [ $AUTOSAVE -eq 1 ]
then
   #Send save-all to the console
   screen -x $SCREENNAME -X stuff "$(printf "\rsave-all\r")"
   # sleep 2 -- no need for this
fi

# --Cron Job Install--
if [ $CRONJOB -eq 1 ]
then

   #Check if user can use crontab
   if [ -f "/etc/cron.allow" ]
   then
      EXIST=$(grep "$USER" < /etc/cron.allow)
      if [ "$EXIST" != "$USER" ]
      then
         echo "Sorry. You are not allowed to edit cronjobs."
         exit
      fi
   fi

   #Work out crontime
   if [ $UPDATEMINS -eq 0 -o $UPDATEMINS -lt 0 ]
   then
      MINS="*"
   else
      MINS="*/$UPDATEMINS"
   fi

   #Check if cronjob exists, if not then create.
   crontab -l > .crons
   EXIST=$(crontab -l | grep "$0" | cut -d";" -f2)
   CRONSET="$MINS * * * * cd $PWD;$0"

   if [ "$EXIST" == "$0" ]
   then

      #Check if cron needs updating.
      THECRON=$(crontab -l | grep "$0")
      if [ "$THECRON" != "$CRONSET" ]
      then
         CRONS=$(crontab -l | grep -v "$0")
         echo "$CRONS" > .crons
         echo "$CRONSET" >> .crons
         crontab .crons
         echo "Cronjob has been updated"
      fi

      rm .crons
      exit
   else
      crontab -l > .crons
      echo "$CRONSET" >> .crons
      crontab .crons
      rm .crons
      echo "Autobackup has been installed."
      exit
   fi

fi
