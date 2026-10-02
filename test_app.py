from fastapi import FastAPI

app = FastAPI(title="Drone Detector API", version="1.0.0")

@app.get("/")
async def root():
    return {"message": "Drone Detector API is running!", "docs": "/docs"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "drone-detector"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)
