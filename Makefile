.PHONY: common
common:
	cd ${PWD} && cp -a . ${RELEASEDIR}/frontend
	mkdir -p ${RELEASEDIR}/frontend/data

.PHONY: dev
dev: common
	cd ${PWD} && cp -a static/vue.dev.js ${RELEASEDIR}/frontend/static/vue.js

.PHONY: prod
prod: common
	cd ${PWD} && cp -a wsgi.py ${RELEASEDIR}/frontend/
	cd ${PWD} && cp -a static/vue.min.prod.js ${RELEASEDIR}/frontend/static/vue.js
	-cd ${PWD} && cp robotfx-nginx.conf /etc/nginx/sites-available/ 2>/dev/null || :
	-cd ${PWD} && ln -sf /etc/nginx/sites-available/robotfx-nginx.conf /etc/nginx/sites-enabled/ 2>/dev/null || :
