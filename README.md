# code-docker-blender

> **⚠️ 실험 단계 (2026-10).** 스텁 스택(`test/run.sh`)과 실제 Claude Code CLI로는 끝까지
> 검증했지만, 실제 code-docker 스택에 붙여 router VNC 탭까지 확인하지는 않았습니다.

[code-docker](https://github.com/qwreey/code-docker)에 **Blender를 붙이는 프로바이더**입니다.
GUI Blender가 상시 떠 있고, 그 한 세션을 두 경로로 씁니다.

- **MCP** → code-docker 안의 에이전트가 모델을 만들고, 렌더하고, 화면을 보고, 고칩니다
  ([Blender Lab 공식 MCP](https://www.blender.org/lab/mcp-server/), 토큰 인증)
- **VNC** → router를 거쳐 사람이 같은 화면을 보고 직접 만집니다

GPU(`/dev/dri`)를 그대로 써서 EEVEE 렌더 한 장이 1~2초입니다. 컨테이너에는 인터넷이 없습니다.

## 붙이기

`ootb-extra.sh`에 이 레포의 git URL을 넣으면 아래가 자동으로 됩니다
([ootb-manifest.md](https://github.com/qwreey/code-docker/blob/HEAD/docs/tips/ootb-manifest.md)).

- `extra-include.yml`에 `builds/code-docker-blender/code-docker-blender.yml` 추가
- `.env.router`의 `ROUTER_EXTRA_ALLOWED_TARGET_HOSTS`에 `blender-vnc` 추가
- `.env`에 `BLENDER_MCP_TOKEN` 생성

수동으로 하려면 위 세 가지를 직접 하고(토큰은 `openssl rand -hex 32`), code-docker 디렉터리에서:

```sh
docker compose build code-docker-blender
docker compose up -d   # router와 code-docker도 새 망/볼륨 때문에 다시 만들어집니다
```

## Claude Code에 연결

code-docker 안의 셸에서 한 번:

```sh
claude mcp add --transport http blender http://blender:8765/ \
  --header "Authorization: Bearer $BLENDER_MCP_TOKEN" \
  -s user
claude mcp list   # blender: ... (HTTP) - ✔ Connected
```

`$BLENDER_MCP_TOKEN`은 오버레이가 code-docker 컨테이너에도 넣어주므로 그대로 풀립니다.
**`-s project`는 쓰지 마세요** - 토큰이 박힌 `.mcp.json`이 레포에 커밋됩니다.

### 모델링 서브에이전트

게임을 만드는 에이전트가 모델링을 맡길 수 있게 서브에이전트 템플릿을 같이 넣어 둡니다.

```sh
mkdir -p ~/.claude/agents
cp /run/code-docker-blender/blender-modeler.md ~/.claude/agents/
```

만들기 → 여러 각도로 렌더해서 직접 보기 → 고치기 → `.glb`/`.fbx` 내보내기까지 하고,
경로와 삼각형 수를 보고합니다. 복사본이니 프로젝트에 맞게 고쳐 쓰세요.

## 화면 보기

router의 VNC 탭에서 **`rfb` 백엔드로 `blender-vnc:5900`** 을 등록합니다. 대상 호스트는
`code-docker-blender`가 아니라 `blender-vnc`입니다 - 컨테이너가 두 망에 붙어 있어서 이름이
두 IP로 풀리고, VNC는 VNC 망 쪽에만 열려 있습니다.

창은 Blender 하나뿐입니다. Blender를 종료하면 바로 다시 뜨고(저장 안 한 씬은 사라짐),
바탕화면 우클릭 메뉴의 **Start Blender**로도 띄울 수 있습니다.

VNC에 맞춰 바꿔 둔 Blender 설정이 두 가지 있습니다.

- **뷰포트 조작** - 중간 드래그(회전), Shift+중간 드래그(이동), 내비게이션 기즈모 드래그가
  VNC에서 동작하도록 *Continuous Grab*을 꺼 두었습니다. 대신 드래그가 창 가장자리에서 멈춥니다.
- **렌더 결과 창 없음** - 에이전트가 렌더할 때마다 Render Result 창이 화면을 덮지 않도록
  결과 표시를 *Keep User Interface*로 두었습니다. 마지막 렌더는 **F11**로 볼 수 있습니다.

## 파일

**`/code/blender`** 가 두 컨테이너에 같은 경로로 붙어 있는 공유 디렉터리입니다
(`code-docker-blender-work` 볼륨). `.blend`, 내보낸 모델, 렌더 PNG는 여기 둡니다.

- MCP의 `render_*_to_path` 결과와 Blender 자동 저장은 `/code/blender/.tmp/` 아래에 생깁니다.
- dind 안에서 띄운 컨테이너에는 이 디렉터리가 비어 보입니다(dind는 `/code`만 같은 경로로 봅니다).

## 비용

Radeon 780M에서 잰 값입니다(30초 평균).

| 상태 | GPU | SoC 전력 | CPU | RAM |
|---|---|---|---|---|
| 아무것도 안 함 | 1.0% | 4.9W | — | — |
| 대기 (GUI 상주) | 1.0% | 4.7~4.8W | 약 1% | 약 700MB |
| 초당 5회 연속 편집 | 12.6% | 5.8W | 17.5% | 약 710MB |

대기 중에는 GPU와 전력이 거의 그대로이고, 다시 그릴 일이 생길 때만 비용이 듭니다.

## 설정

모두 **code-docker의 `.env`** 에 넣습니다 - [.env.example](.env.example) 참고.

| 변수 | 기본값 | |
|---|---|---|
| `BLENDER_MCP_TOKEN` | (생성됨) | MCP 토큰. 비어 있으면 MCP가 뜨지 않습니다 |
| `BLENDER_SCREEN_SIZE` | `1920x1080` | 화면 해상도 |
| `BLENDER_WORK_DIR` | `/code/blender` | 공유 디렉터리 경로 |
| `BLENDER_VNC_PASSWORD` | (없음) | wayvnc 자체 비밀번호 |

## 제약

- **인터넷 없음** - 확장 설치, 온라인 에셋, 다운로드가 안 됩니다. 의도된 것입니다
  ([CLAUDE.md](CLAUDE.md)의 "Networks" 참고).
- **GPU는 Mesa만** - AMD/Intel은 그대로 됩니다. NVIDIA 독점 드라이버는 이미지에 없습니다.
  `/dev/dri`가 없는 호스트에서는 컨테이너가 뜨지 않습니다.
- **Blender 환경설정은 이미지에 있습니다** - GUI에서 바꾼 설정은 컨테이너를 다시 만들면 사라집니다.

## 테스트

```sh
test/run.sh   # 스텁 스택으로 빌드 → MCP/렌더/파일 공유 → 망 경계 검사 → 정리
```

실제 스택과 겹치지 않게 `PREFIX=bltest-`로 띄웁니다. `KEEP=1`이면 끝나도 내리지 않습니다.
