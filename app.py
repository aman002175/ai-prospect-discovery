"""
Entrypoint for deployment platforms (Hugging Face Spaces, Render, Koyeb).
Binds to port 7860 (Hugging Face default) or the PORT environment variable.
"""
import os
import uvicorn
from app.main import app

# Optional: If deployed on Hugging Face Spaces (Gradio SDK), mount interactive UI at /ui
try:
    import gradio as gr
    from app.services.prospect_service import prospect_service

    async def run_discovery(query: str):
        if not query or not query.strip():
            return {"error": "Please enter a valid query."}
        res = await prospect_service.discover_prospects(query.strip())
        return res.model_dump()

    ui = gr.Interface(
        fn=run_discovery,
        inputs=gr.Textbox(label="Query", placeholder="e.g. Football lovers in Washington DC in USA", lines=2),
        outputs=gr.JSON(label="Result"),
        title="AI-Powered Prospect Discovery API",
        flagging_mode="never"
    )
    app = gr.mount_gradio_app(app, ui, path="/ui")
except ImportError:
    pass

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)
