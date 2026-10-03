import requests

import core.llm as llm


def test_ollama_vision_uses_local_endpoint_without_hailo(monkeypatch):
    monkeypatch.setattr(llm, "VISION_BACKEND", "ollama")
    monkeypatch.setattr(llm, "VISION_MODEL", "moondream")
    monkeypatch.setattr(llm, "_get_vlm", lambda: (_ for _ in ()).throw(AssertionError("Hailo used")))
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "A red square."}}

    def post(url, **kwargs):
        sent.update(kwargs["json"])
        return Response()

    monkeypatch.setattr(llm.requests, "post", post)
    brain = llm.Brain(persist=False)
    assert brain.analyze_image("data:image/png;base64,YWJj", "What is this?") == "A red square."
    assert sent["model"] == "moondream"
    assert sent["messages"][0]["images"] == ["YWJj"]
    assert brain.history[-1] == {"role": "assistant", "content": "A red square."}


def test_failed_cpu_vision_does_not_leave_unanswered_history(monkeypatch):
    monkeypatch.setattr(llm, "VISION_BACKEND", "ollama")

    def fail(*args, **kwargs):
        raise requests.Timeout("test timeout")

    monkeypatch.setattr(llm.requests, "post", fail)
    brain = llm.Brain(persist=False)
    previous = list(brain.history)
    assert "aren't working" in brain.analyze_image("YWJj", "Describe it")
    assert brain.history == previous
