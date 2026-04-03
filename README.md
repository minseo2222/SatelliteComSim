# Satellite Communication Security Simulator

위성 통신 환경을 리눅스 PC에서 실험할 수 있게 만든 프로젝트입니다.

이 저장소에는 아래 2가지가 함께 들어 있습니다.

- `cFS`: NASA Core Flight System 기반 위성 소프트웨어
- `newGS`: 우리가 수정한 지상국 소프트웨어

이 프로젝트의 기본 실험 흐름은 다음과 같습니다.

1. 지상국에서 Sample App 텍스트 명령을 보냅니다.
2. cFS가 그 명령을 받습니다.
3. cFS가 받은 텍스트를 텔레메트리로 다시 지상국에 내려보냅니다.
4. 지상국에서 송신값, 수신값, BER, 유사도, 공격 결과를 확인합니다.

또한 중간에 통신 공격 기능을 넣어서 `패킷 드랍`, `재밍`, `리플레이`, `지연`, `지터`, `BER` 등을 시험할 수 있습니다.

## 1. 이 README가 안내하는 대상

이 문서는 다음 사람을 기준으로 작성했습니다.

- Python, GNU Radio, cFS를 처음 설치하는 사람
- 이 저장소를 다른 Linux PC에 그대로 받아서 실행해보고 싶은 사람

가능하면 명령어를 그대로 복사해서 실행할 수 있게 적었습니다.

## 2. 권장 환경

가장 권장하는 환경은 다음과 같습니다.

- Ubuntu 22.04 또는 Ubuntu 24.04
- 인터넷 연결 가능
- GUI 환경 가능
- `sudo` 사용 가능

다른 Debian 계열 Linux도 가능하지만, 처음이면 Ubuntu가 가장 편합니다.

## 3. 저장소 구조

중요한 폴더만 보면 됩니다.

- `src/cFS`
  NASA cFS 소스 코드입니다.
- `src/newGS`
  지상국 GUI와 통신 실험 코드입니다.
- `runtime/linux-x86_64/cpu1`
  cFS 실행 파일과 런타임 파일이 모이는 폴더입니다.
- `src/newGS/Subsystems/cmdUtil`
  cFS 명령 패킷을 만드는 도구입니다.
- `src/gr-leo`
  GNU Radio OOT 모듈 소스입니다.

현재 프로젝트를 실제로 실행할 때 가장 자주 쓰는 폴더는 아래 2개입니다.

- `runtime/linux-x86_64/cpu1`
- `src/newGS`

## 4. 먼저 설치해야 할 프로그램

터미널을 열고 아래 명령을 순서대로 실행하세요.

```bash
sudo apt update
sudo apt install -y \
  git build-essential gcc g++ make cmake \
  python3 python3-pip \
  python3-pyqt5 python3-zmq python3-numpy python3-opengl python3-pil python3-bs4 \
  gnuradio \
  libgl1-mesa-dev libglu1-mesa-dev libcanberra-gtk-module mesa-utils
```

그 다음 `trimesh`를 설치합니다.

```bash
python3 -m pip install --user trimesh
```

설치가 끝났는지 간단히 확인하려면:

```bash
python3 - <<'PY'
import PyQt5, zmq, numpy, trimesh, OpenGL
print("Python packages OK")
PY
```

오류가 없으면 준비가 된 것입니다.

## 5. 저장소 받기

이미 이 저장소가 있다면 이 단계는 건너뛰어도 됩니다.

```bash
git clone <이 저장소 주소>
cd SatelliteComSim
```

예를 들어 저장소 이름이 `SatelliteComSim`이라면 위와 같이 받으면 됩니다.

## 6. cFS 빌드

다른 Linux에서 처음 실행할 때는 cFS를 한 번 다시 빌드하는 것을 권장합니다.

```bash
cd ~/SatelliteComSim/src/cFS
make SIMULATION=native prep
make
make install
```

이 과정은 시간이 조금 걸릴 수 있습니다.

정상적으로 끝나면 `runtime/linux-x86_64/cpu1` 쪽에 실행 파일과 `.so` 파일이 준비됩니다.

## 7. cmdUtil 다시 빌드하기

이 프로젝트에는 `cmdUtil` 실행 파일이 이미 들어 있지만, 다른 Linux에서 아키텍처가 다르거나 실행이 안 될 수 있습니다.
그럴 때는 아래처럼 다시 빌드하면 됩니다.

```bash
cd ~/SatelliteComSim/src/newGS/Subsystems/cmdUtil
make
```

정상적으로 끝나면 `cmdUtil` 실행 파일이 다시 만들어집니다.

## 8. 실행 방법

이 프로젝트는 터미널 2개를 쓰는 것이 가장 편합니다.

### 8-1. 첫 번째 터미널: cFS 실행

```bash
cd ~/SatelliteComSim/runtime/linux-x86_64/cpu1
sudo ./core-cpu1
```

중요:

- `./core-cpu1`만 실행했을 때 `Operation not permitted` 오류가 나면 `sudo ./core-cpu1`로 실행하세요.
- 반드시 `runtime/linux-x86_64/cpu1` 폴더 안에서 실행하세요.

정상이라면 아래와 비슷한 로그가 보여야 합니다.

- `CI_LAB listening on UDP port: 1234`
- `TO Lab Initialized`
- `SAMPLE App Initialized`

### 8-2. 두 번째 터미널: 지상국 실행

```bash
cd ~/SatelliteComSim/src/newGS
python3 run_com.py
```

정상이라면 아래 프로세스가 자동으로 뜹니다.

- `test4.py`
- `test3.py`
- `test2.py`
- `test1.py`
- `GroundSystem.py`

`run_com.py`는 시작 전에 예전 프로세스를 정리하도록 되어 있습니다.

## 9. 실제 사용 순서

프로그램이 뜨면 아래 순서로 사용하면 됩니다.

1. `GroundSystem` 창에서 필요한 설정을 확인합니다.
2. `Start Command System`을 실행합니다.
3. `Start Telemetry`를 실행합니다.
4. `Sample App` 페이지를 열어서 텍스트를 보냅니다.
5. `Sample App Display Page`에서 송신/수신 결과를 확인합니다.

확인 가능한 정보:

- 보낸 텍스트
- 받은 텍스트
- BER
- Similarity
- 상세보기에서 송신 비트 / 수신 비트
- 공격 적용 결과

## 10. 종료 방법

### 지상국 종료

`run_com.py`를 실행한 터미널에서 `Ctrl + C`를 누르세요.

### cFS 종료

`core-cpu1`를 실행한 터미널에서 `Ctrl + C`를 누르세요.

## 11. 자주 생기는 문제와 해결 방법

### 문제 1. `./core-cpu1` 실행 시 권한 오류가 납니다

예:

```text
Could not setschedparam in main thread: Operation not permitted
```

해결:

```bash
sudo ./core-cpu1
```

### 문제 2. cFS는 떴는데 명령이 안 먹습니다

먼저 아래 로그가 보이는지 확인하세요.

- `CI_LAB listening on UDP port: 1234`
- `TO Lab Initialized`
- `SAMPLE App Initialized`

이게 안 보이면 cFS가 정상 시작되지 않은 것입니다.

### 문제 3. `Sample App` 명령을 보냈는데 cFS 콘솔에 `Invalid ground command code: CC = 3`가 뜹니다

이 경우는 런타임의 `sample_app.so`가 오래된 파일일 가능성이 큽니다.

다시 아래를 실행하세요.

```bash
cd ~/SatelliteComSim/src/cFS
make
make install
```

### 문제 4. 지상국 실행 시 `Address already in use`가 뜹니다

보통 예전 프로세스가 남아 있는 경우입니다.

현재 `run_com.py`는 이런 상황을 자동으로 어느 정도 정리합니다.
그래도 계속 뜨면 한 번 더 `Ctrl + C`로 완전히 종료한 뒤 다시 실행하세요.

### 문제 5. 모델링 창 색이 이상하게 보입니다

최근 버전에서는 이 문제를 수정했습니다.
그래도 이상하면 `GroundSystem`을 완전히 껐다가 다시 실행하세요.

### 문제 6. 공격이 꺼져 있는데도 `Lost`로 보입니다

예전 로그 파일 형식이 남아 있을 수 있습니다.

아래를 해보세요.

1. `Start Telemetry`를 다시 실행
2. `Sample App Display Page`에서 로그 초기화
3. 다시 테스트

## 12. 공격 기능 설명

현재 공격 기능은 cFS 헤더 전체를 부수는 방식이 아니라, 가능한 한 `Sample App` 텍스트 payload 위주로 동작하도록 맞춰져 있습니다.

지원하는 기능:

- `Drop`
  패킷 자체를 버립니다.
- `Jamming`
  payload 일부를 랜덤 바이트로 바꿉니다.
- `Replay`
  같은 패킷을 일정 시간 뒤에 한 번 더 보냅니다.
- `BER / Delay / Jitter`
  채널 품질을 조절합니다.

중요:

- CCSDS 헤더
- MID
- CC
- 길이 필드

같은 부분을 함부로 깨면 cFS가 패킷을 아예 인식하지 못하므로, 현재 구현은 payload 중심으로 안전하게 맞춰져 있습니다.

## 13. 3D 모델링과 설정 반영

현재 3D 화면에서는 아래 항목이 반영됩니다.

- 위성 크기
- 위성 속도
- 궤도 반경
- 궤도 경사각
- 이심률
- 기지국 위치
- 최소 고도각
- BER / Delay / Jitter 기반 링크 색 변화

즉 설정 창에서 값을 바꾸면 통신 설정뿐 아니라 시각화도 같이 바뀝니다.

## 14. `gr-leo` 폴더에 대해

`src/gr-leo`는 GNU Radio OOT 모듈 소스입니다.

현재 프로젝트를 기본 실행하는 데는 `GNU Radio` 패키지가 더 중요하고, `gr-leo` 자체를 따로 설치하지 않아도 현재 `newGS` 기본 흐름은 동작합니다.

다만 나중에 `gr-leo`를 따로 연구하거나 다시 연결하고 싶다면, 그 폴더의 README를 참고해서 별도로 빌드하면 됩니다.

## 15. 추천 실행 순서 한 번에 보기

처음 설치한 뒤 가장 추천하는 순서는 아래입니다.

```bash
cd ~/SatelliteComSim/src/cFS
make SIMULATION=native prep
make
make install
```

```bash
cd ~/SatelliteComSim/src/newGS/Subsystems/cmdUtil
make
```

첫 번째 터미널:

```bash
cd ~/SatelliteComSim/runtime/linux-x86_64/cpu1
sudo ./core-cpu1
```

두 번째 터미널:

```bash
cd ~/SatelliteComSim/src/newGS
python3 run_com.py
```


## 16. 참고 자료

- NASA cFS
- NASA cFS-GroundSystem
- GNU Radio
- gr-leo
