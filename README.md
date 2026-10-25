# Animai ([animai.design](https://www.animai.design))
<img width="2518" height="1212" alt="Screenshot 2026-10-25 014208" src="https://github.com/user-attachments/assets/3c3058cc-bc83-4f60-a8f7-02cf58ad0030" />
<img width="2249" height="1622" alt="Frame 2" src="https://github.com/user-attachments/assets/dfb3dded-0c9d-4939-bf34-39b6aa148109" />

### Make high quality animated educational videos for any subject, entirely in code! And, scroll through an endless feed of these videos and learn something new.

## Links
Live: https://animai.design/

Devpost: https://devpost.com/software/animai-4ipdlz

## What is Animai?
The Animai engine is a code library that allows anyone to make a high quality animated educational video entirely in Python code. It exposes functions with pre-built visual components, animations, color themes, voiceover, and a custom renderer, so you (or your agent!) just writes code for the video you want to make and it returns the rendered output video.

The Animai website is a social platform where users can create, share, and explore these animated educational videos. You can search for topics or scroll endlessly in a reels-style algorithm (but you're learning instead of rotting!). You can also create your own content with a topic, context, and style of your choice, which is fed into an agent which researches, synthesizes, and creates the video for everyone to watch.

## Technical Implementation
For the engine, we built a Python animation library on a WebGL-derived renderer, adding reusable educational components, visual themes, and synchronized voice narration. In the platform, Claude agents write and review the animation code in a pipeline, while Apify gathers relevant Youtube transcripts for research into other similar videos. FastAPI runs the generation pipeline, and Convex handles the data layer with accounts + realtime updates (eg. views and likes on videos).

Built with: anthropic-api, apify, claude, cloudflare-tunnel, convex, css, edge-tts, fastapi, ffmpeg, figma, html, httpx, javascript, jwt, latex, matplotlib, node.js, numpy, pyav, pydantic, python, scipy, typescript, wgpu, wgsl
