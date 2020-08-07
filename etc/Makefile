.PHONY: common
common:
	-cd ${PWD} && cp robotfx.sh ${RELEASEDIR}/etc
	-cd ${PWD} && cp robotfx_test.sh ${RELEASEDIR}/etc
	-cd ${PWD} && cp -a fxgo-config ${RELEASEDIR}/etc
	-cd ${PWD} && cp -a fixdicts ${RELEASEDIR}/etc
	-cd ${PWD} && cp -a init ${RELEASEDIR}/etc
	-cd ${PWD} && cp env ${RELEASEDIR}/etc/env
	-cd ${PWD} && cp services ${RELEASEDIR}/etc/services
	-cd ${PWD} && cp rfxconfig.dev.json ${RELEASEDIR}/etc/rfxconfig.json
	-rm -f ${RFX_HISTORY_DIR}/transactions.db


.PHONY: dev
dev: common
	-cd ${PWD} && cp rfxconfig.dev.json ${RELEASEDIR}/etc/rfxconfig.json


.PHONY: prod
prod: common
	-cd ${PWD} && cp rfxconfig.prod.json ${RELEASEDIR}/etc/rfxconfig.json
