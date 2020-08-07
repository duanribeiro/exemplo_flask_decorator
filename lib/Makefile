.PHONY: clean cleandir
clean cleandir:
	-rm -fv *pyc
	-rm -frv web

.PHONY: dev prod
dev prod:
	mkdir -p ${RELEASEDIR}/lib
	cd ${PWD} && cp libbus2.py ${RELEASEDIR}/lib
	cd ${PWD} && cp libdatabus.py ${RELEASEDIR}/lib
	cd ${PWD} && cp libdatabus_utils.py ${RELEASEDIR}/lib
	cd ${PWD} && cp libep.py ${RELEASEDIR}/lib
	cd ${PWD} && cp libtransactions.py ${RELEASEDIR}/lib
	cd ${PWD} && cp libutils.py ${RELEASEDIR}/lib
	cd ${PWD} && cp messages.py ${RELEASEDIR}/lib
	cd ${PWD} && cp taskproxy.py ${RELEASEDIR}/lib
	cd ${PWD} && cp receipts.py ${RELEASEDIR}/lib
	cd ${PWD} && cp -a pricing ${RELEASEDIR}/lib
	cd ${PWD} && cp -a history ${RELEASEDIR}/lib
	cd ${PWD} && cp -a mktdata ${RELEASEDIR}/lib
	cd ${PWD} && cp -a translate ${RELEASEDIR}/lib
	cd ${PWD} && cp -a validation ${RELEASEDIR}/lib
	cd ${PWD} && cp liblog.py ${RELEASEDIR}/lib
	cd ${PWD} && cp libflask.py ${RELEASEDIR}/lib
	cd ${PWD} && cp libexceptions.py ${RELEASEDIR}/lib
	cd ${PWD} && cp librisk.py ${RELEASEDIR}/lib
	cd ${PWD} && cp libfixconnection.py ${RELEASEDIR}/lib

