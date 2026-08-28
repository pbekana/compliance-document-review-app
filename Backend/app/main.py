from fastapi import FastAPI
app = FastAPI(
    title="Compliance Document Review App",
    version="1.0.0"
)

@app.get("/heath")
def health_check():
  return {
    "status":"health",
    "message":"Backend is running smoothly  is running successfully"
      }