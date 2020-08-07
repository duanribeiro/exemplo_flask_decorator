#!/usr/bin/env python3
from application import create_app

app = create_app()

if __name__ == '__main__':
    # print(app.url_map, flush=True)
    app.run(host='0.0.0.0', port=8808, debug=True, use_reloader=True)
