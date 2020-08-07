#!/bin/sh

BASEDIR=$(dirname "$0")
. ${BASEDIR}/env
export current_dir=${ROBOTFXDIR}/etc

start()
{
    rm ${ROBOTFXDIR}/test/fixclient/store_client/* 2>/dev/null
    rm ${ROBOTFXDIR}/test/fixserver/store_server_client/* 2>/dev/null
    rm ${ROBOTFXDIR}/test/fixserver/store_server_gateway/* 2>/dev/null
    rm ${ROBOTFXDIR}/store_client/* 2>/dev/null
    rm ${ROBOTFXDIR}/store_server_client/* 2>/dev/null
    rm ${ROBOTFXDIR}/store_server_gateway/* 2>/dev/null
    rm /var/tmp/rfx_quickfix_store/* 2>/dev/null
}

stop()
{
    echo 
}

restart()
{
    echo
}

case "$1" in
        start)
            start
                ;;
        stop)
                ;;
        status)
                ;;
        restart)
            stop
            start
            ;;
        cmd)
            cmd
            ;;
        *)
            exit 1
            ;;
esac

LIST="`cat ${ROBOTFXDIR}/etc/services`"

for service in ${LIST}
do
    OK=1
    for not in $2;
    do 
        if [ $service = $not ]
        then
            OK=0
        fi
    done

    if [ $OK -eq 1 ]
    then
        ${current_dir}/init/$service $1
    else
        echo Do not act on: $service
    fi
done
