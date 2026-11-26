set -eu
mkdir installing
echo start >> events
while [ ! -e release ]; do sleep 0.02; done
echo end >> events
rmdir installing
test ! -e fail-install
