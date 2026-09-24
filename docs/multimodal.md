# Multimodal status

CARVE can pass image or video content to the multimodal Qwen3.8 backbone while
retaining the same one-token candidate readout.

This is an experimental engineering capability, not an accuracy claim. No
representative multimodal decision benchmark was run.

The `media` extension accepts OpenAI-compatible `image_url` and `video_url`
parts:

```json
{
  "model": "CARVE-27B",
  "state": "Inspect the attached image.",
  "media": [{
    "type": "image_url",
    "image_url": {"url": "data:image/png;base64,..."}
  }],
  "questions": {
    "dominant_color": {
      "type": "choice",
      "instructions": "What is the dominant image color?",
      "criteria": {"red": null, "green": null, "blue": null}
    }
  }
}
```

A generated 128×128 red image passed an end-to-end test: CARVE selected `red`
with raw candidate probability 0.9998 using 173 input tokens and one output
token. This proves request plumbing only. Image count, resolution, video
duration, and vision-token count will affect latency and throughput.

The reproducibility record is `artifacts/multimodal-smoke.json`.
