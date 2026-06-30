FROM runpod/base:0.6.2-cuda12.1.0

# use `python3 -m pip` so pip installs into the SAME interpreter that runs handler.py
# (runpod/base ships multiple pythons; a bare `pip` can install where python3 won't find it)
COPY requirements.txt /requirements.txt
RUN python3 -m pip install --no-cache-dir -r /requirements.txt

# bake both models into the image at build time — avoids multi-GB downloads on every cold start.
# Hebrew-specialised model (default) + general multilingual model (English / auto-detect).
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('ivrit-ai/whisper-large-v3-turbo-ct2', device='cpu', compute_type='int8')"
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('large-v3', device='cpu', compute_type='int8')"

COPY handler.py /handler.py

CMD ["python3", "-u", "/handler.py"]
