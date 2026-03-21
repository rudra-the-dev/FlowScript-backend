from flask import Flask
from vision import vision_bp

app = Flask(__name__)
app.register_blueprint(vision_bp)

@app.route('/')
def index():
    return {
        "app": "FlowScript Backend",
        "version": "2.0",
        "status": "running",
        "endpoints": {
            "health": "/vision/health",
            "next_action": "/vision/next-action"
        }
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
