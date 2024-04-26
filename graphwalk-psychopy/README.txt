Download https://github.com/uciccnl/graphwalk/archive/refs/heads/master.zip and unzip
Open Terminal and run the following commands:
cd ~/Downloads/graphwalk-master/
./graphwalk-psychopy/graphwalk.py <subject id>

Note:
'a', 's', 'd' are the response buttons
'q' during a trial will quit
'n' during a trial will skip to the next phase

If you quit (or if the script crashed) and you want to continue from where you left off, you can run:
./graphwalk-psychopy/graphwalk.py --continue <same subject id from before>

Results files can be found in graphwalk-master/graphwalk-psychopy/results/