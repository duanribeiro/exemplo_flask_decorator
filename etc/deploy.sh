#!/bin/sh

docker build --target=prod -t robotfx:${1} .
mkdir temp_deploy && cd temp_deploy
mkdir robotfx-${1} && chmod 775 robotfx-${1} && cd robotfx-${1}
mkdir data && chmod 775 data && cd data
docker save --output robotfx-${1}.img robotfx:${1} && chmod 664 robotfx-${1}.img
cd ../..
tar -zcvf robotfx-${1}.tar.gz robotfx-${1}
scp robotfx-${1}.tar.gz ${2}@104.197.122.76:~/copyDir
ssh -T ${2}@104.197.122.76 << EOF
    cd copyDir
    sudo mv robotfx-${1}.tar.gz /var/www/html/
EOF
