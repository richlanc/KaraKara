#!/usr/bin/env bash

set -e

# Variables --------------------------------------------------------------------

HOME="/home/vagrant"
SHARE="/vagrant"
GIT_REPO="https://github.com/calaldees/KaraKara.git"

# Check if installation required

if [ -f "$HOME/setup" ]
then
	echo "Install previously completed"
else
	echo "Installing packages"

# Root Setup -------------------------------------------------------------------

#if dpkg -s git ; then
#    echo prerequesits already installed
#else
apt-get update
apt-get install -y git make curl nfs-common portmap
locale-gen en_US.UTF-8
#fi


# User Setup -------------------------------------------------------------------

sudo -u vagrant sh << EOF
set -e

# Vagrant does not update the HOME env when switching to normal 'vagrant' user
HOME="/home/vagrant"

cd $HOME
if [ -f "KaraKara" ]
then
	echo "codebase already checked out"
else
	git clone $GIT_REPO
fi

# Setup Website Python Project
cd $HOME/KaraKara/website
make install
make test
make ini_production

echo 'Setup nginx and PostgreSQL'
cd $HOME/KaraKara/mediaserver
sudo make setup
make captive_portal_disable

echo 'Setup AdminDashboard requirements'
cd $HOME/KaraKara/admindashboard
make install_linux
# TODO - In future need to start elastic search on startup and alias logstash

echo 'Symlink the nginx static file path with the hosts vagrant share'
ln -s /vagrant $HOME/KaraKara/mediaserver/www/files

echo 'Import all track data from the host system'
cd $HOME/KaraKara/website
make init_db_production

echo 'Installation complete'
touch $HOME/setup

EOF

fi


# VM Startup -------------------------------------------------------------------

echo 'Start nginx'
cd $HOME/KaraKara/mediaserver
make start_nginx

echo 'Start KaraKara daemon'
sudo -u vagrant sh << EOF
cd $HOME/KaraKara/website
make import_tracks_production
make start_webapp_daemon

EOF
