# Git 변경 내용으로 커밋·PR 문안 만들기

이 도구는 선택한 로컬 Git 저장소의 변경 내용을 읽어 커밋 제목 또는 풀 리퀘스트(PR) 문안을 제안하는 명령줄 프로그램입니다. 변경 내용을 커밋하거나 PR을 생성하지 않습니다.

## 준비와 실행

Python 3.10 이상과 Git이 필요합니다. 실행 시 Python 표준 라이브러리만 사용하므로 패키지를 추가로 설치할 필요가 없습니다. 이 저장소를 원하는 위치에 내려받거나 압축을 풀고, 문안을 만들 **대상 Git 저장소**로 이동해 실행하세요. 아래 예시에서 `TOOL_DIR`은 이 도구의 디렉터리이며, 원하는 이식 가능한 경로로 바꾸면 됩니다.

```sh
cd /path/to/your-git-repository
python3 /path/to/TOOL_DIR/main.py commit --dry-run
python3 /path/to/TOOL_DIR/main.py commit
python3 /path/to/TOOL_DIR/main.py pr --staged
```

이 도구 디렉터리에서는 Make 명령으로도 실행할 수 있습니다. `commit`과 `pr`은 문안만 생성하며 Git 커밋이나 PR을 만들지 않습니다. `preview-commit`과 `preview-pr`은 실제 변경 내용을 읽어 요청 JSON을 출력하지만 API 키 조회나 네트워크 요청은 하지 않습니다.

```sh
make preview-commit
make preview-pr ARGS='--staged'
make commit
make pr ARGS='--staged --safe-mode'
make preview-commit REPO='/path/to/target repo' ARGS='--staged --model example-model'
make pr REPO='/path/to/target repo' ARGS='--staged'
```

`REPO`를 생략하면 현재 Make 작업 디렉터리의 저장소를 사용합니다. 다른 저장소를 지정할 때는 공백이 있는 경로도 위처럼 따옴표로 감싸세요. `ARGS`는 선택한 CLI 명령에 옵션을 전달합니다. 네 대상의 전체 옵션은 `python3 main.py commit --help` 또는 `python3 main.py pr --help`에서 확인할 수 있습니다.

실제 문안 생성에는 `AI_API_KEY` 환경 변수가 필요합니다. 비어 있거나 없으면 `OPENAI_API`를 대신 사용합니다. 예를 들어 실행 전에 `export AI_API_KEY='your-key'`로 설정할 수 있습니다. `.env` 파일은 자동으로 읽지 않습니다. 요청은 고정된 `https://copa.codyssey.kr/v1/chat/completions` 엔드포인트로 한 번 전송하며 자동 재시도하지 않습니다. 기본 모델은 `gpt-5-mini`이고 `--model`로 바꿀 수 있습니다.

## 변경 내용 선택과 옵션

`commit`은 커밋 제목, `pr`은 PR 제목과 본문을 제안합니다. 기본 선택은 스테이징되지 않은 추적 파일의 diff이며, `--staged`는 스테이징된 diff를 사용합니다. 추적되지 않은 파일은 미리보기에서 경로만 표시하고 내용은 읽지 않습니다. 새 파일의 내용을 포함하려면 먼저 `git add`로 스테이징한 다음 `--staged`를 사용하세요. 선택한 변경이 없으면 안내 문구를 출력하고 종료합니다. 추적되지 않은 파일만 있을 때 일반 생성은 스테이징 안내 오류를 출력합니다.

`--dry-run`은 선택한 Git 내용과 제안된 요청 본문을 JSON으로 출력합니다. 이 모드에서는 API 키를 조회하거나 네트워크를 사용하지 않습니다. 추적 파일의 diff에 민감한 정보가 있으면 출력에도 포함될 수 있으므로 공유 전에 확인하세요.

`--safe-mode`는 diff와 표시 경로의 일반적인 API 키, `api_key`, `token`, `password`, 이메일 패턴을 가리고, 요청과 미리보기에 사용하는 diff를 제한합니다. 생성 문안과 Git 오류도 마스킹합니다. 정규식 기반 마스킹은 모든 비밀을 찾는다고 보장하지 않습니다. 이 모드의 미리보기에는 범위 밖 경로가 드러나지 않도록 상태 목록을 생략합니다. `--max-files`(기본 10)와 `--max-lines`(기본 200)는 safe mode에서 선택된 추적 파일 diff에 적용하는 양의 정수 제한입니다. 파일은 `diff --git` 구간, 줄은 헤더와 메타데이터를 포함한 물리적 diff 줄입니다. 앞에서부터 담으며 마지막 파일 구간은 줄 제한에서 잘릴 수 있습니다. `truncation`에 전체·포함·제외된 파일 구간과 줄 수를 표시합니다. 추적되지 않은 경로도 최대 `max-files`개만 표시하고 제외 수를 알려 줍니다. 생략된 변경 내용은 문안에서 추정하면 안 됩니다.

`--temperature`는 0부터 2까지의 유한한 숫자, `--max-tokens`는 양의 정수를 받아 API 요청에 전달합니다. `--model`은 비어 있지 않아야 합니다. 각 명령의 전체 옵션은 `commit --help` 또는 `pr --help`에서 볼 수 있습니다.

`--convention path.json`은 다음과 같이 네 문자열 필드가 정확히 있는 선택적 JSON 파일을 읽습니다.

```json
{"type":"feat","scope":"example","language":"en","style":"lowercase"}
```

`type`은 `feat`, `fix`, `docs`, `refactor`, `test`, `chore` 중 하나입니다. `scope`는 영문 소문자로 시작하고 소문자·숫자·하이픈으로 이루어진 1~20자 문자열입니다. `language`는 `en` 또는 `ko`, `style`은 `lowercase` 또는 `sentence`입니다. 제목은 `type(scope): `로 시작해야 합니다. 설명 부분에서 `en`은 영문자를 포함하고 한글을 포함하지 않아야 하며, `ko`는 한글을 포함해야 합니다. 첫 글자의 대소문자와 끝 마침표도 기계적으로 검사하지만 완전한 문법 검사는 아닙니다. 파일이 없거나 형식이 잘못되면 API 키 조회 전에 오류가 납니다.

## 출력과 한계

커밋 제목은 최대 72자이며 변경 파일 이름을 포함해야 합니다. 파일 이름이 지나치게 길 때는 파일을 구체적으로 설명할 수 있습니다. PR 제목은 최대 80자이고 본문에 `Why`, `What`, `How to Test` 목록이 들어갑니다. `What`에는 변경 파일 경로가 있어야 하며 테스트 항목은 실행 결과가 아니라 제안 단계입니다. 응답 형식과 파일 근거를 검사하고 유효하지 않으면 오류를 출력합니다. 문안은 선택된 diff에만 근거하므로 특히 diff가 잘렸다면 원본 변경 내용과 대조해 사용하세요.

`main.py`가 진입점입니다. `b62/git_context.py`는 Git 변경 수집, `b62/safety.py`는 마스킹과 diff 제한, `b62/conventions.py`는 문안 규칙 로드, `b62/generation.py`는 요청 구성·전송·검증, `b62/cli.py`는 명령 흐름을 담당합니다.

`make check`는 표준 라이브러리만으로 구문 컴파일, 모듈 import, CLI 도움말을 확인하는 기본 스모크 검사입니다. 실제 생성 흐름이나 API 동작 전체를 검증하지는 않습니다. `make clean`은 프로젝트 루트와 `b62`의 지정된 캐시 경로를 즉시 삭제하며 심볼릭 링크와 심볼릭 링크 아래 경로는 건너뜁니다.

## 출력 예시

아래는 형식을 보여 주기 위한 합성 예시입니다. `demo.txt`의 내용이 `blue`에서 `green`으로 바뀌었다고 가정하며, 두 명령 모두 스테이징된 `demo.txt` 변경을 전제로 합니다. 실제 API가 이 문안을 생성한 것이 아니며 테스트 실행 결과도 아닙니다.

커밋 제목 예시:

```text
demo.txt의 색상 값을 green으로 변경
```

PR 제목과 본문 예시:

```text
demo.txt의 색상 값을 green으로 변경

## Why
- 예시 파일의 색상 값을 갱신합니다.

## What
- demo.txt에서 blue를 green으로 변경합니다.

## How to Test
- 스테이징된 demo.txt 변경을 확인합니다. 이 항목은 실행 결과가 아닌 제안입니다.
```

같은 스테이징 변경을 대상으로 문안을 요청하는 명령은 다음과 같습니다.

```sh
make commit REPO='/path/to/demo repo' ARGS='--staged'
make pr REPO='/path/to/demo repo' ARGS='--staged'
```
