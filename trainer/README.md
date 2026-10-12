# trainer

확정된 오류 라벨만 학습하는 Python 프로세스입니다. 문장 벡터는 파라미터를 학습하지 않는 로컬 해시 `hashing-char-ngram-v1`이고, 그 위에 작은 PyTorch MLP만 학습합니다. 외부 문장 인코더를 받지 않습니다.

백엔드가 학습 조건을 통과한 실행만 `QUEUED`로 만듭니다. 이 프로세스가 claim한 뒤에만 학습하고, 끝나면 기본 모델로 바꾸지 않습니다.

## Windows

CPU 휠을 설치합니다. CUDA 빌드가 이미 있으면 `MAIDOPS_TRAIN_DEVICE=cuda`로 그 장치를 쓸 수 있습니다. CUDA가 없는데 `cuda`를 지정하면 CPU로 바꾸지 않고 학습을 실패로 남깁니다.

```powershell
cd trainer
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]" --extra-index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python -m pytest
$env:MAIDOPS_BACKEND_URL = "http://127.0.0.1:8080"
$env:MAIDOPS_MODEL_DIR = "..\data\models"
$env:MAIDOPS_TRAIN_DEVICE = "auto"
$env:MAIDOPS_CODE_ROOT = ".."
.\.venv\Scripts\python -m maidops_trainer
```

`MAIDOPS_MODEL_DIR`는 백엔드의 같은 값과 같아야 합니다. 모델 파일은 `mv-00000001.pt`처럼 서버가 예약한 이름만 사용합니다.
