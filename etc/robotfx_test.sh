BASEDIR=$(dirname "$0")
. ${BASEDIR}/env
export current_dir=${ROBOTFXDIR}/etc

start()
{
#    echo "START ALL"
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
#    echo "STOP ALL"
}

restart()
{
    echo
#    echo "RESTART ALL"
}

case "$1" in
        start)
            start
                ;;
        stop)
            #stop
                ;;
        status)
            #status
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

${current_dir}/init/rfx-systemd $1
${current_dir}/init/rfx-bpipeconn $1
${current_dir}/init/rfx-fixserver $1
${current_dir}/init/rfx-quote-spot $1
${current_dir}/init/rfx-quote-ndf $1
${current_dir}/init/rfx-neworder $1
${current_dir}/init/rfx-executionack $1
${current_dir}/init/rfx-reject $1
${current_dir}/init/rfx-fxgogwd $1
${current_dir}/init/rfx-legacy_mocks $1
