RUNTIME = None


__all__ = [
    "get_asset_cleanup_targets",
    "count_directory_contents",
    "delete_contents_in_directory",
    "draw_asset_cleanup_menu",
    "confirm_asset_cleanup",
    "run_asset_cleanup",
    "delete_asset_folder_contents",
    "get_optional_package_display_targets",
    "get_optional_package_cleanup_targets",
    "delete_optional_package_files"
]


def bind_runtime(runtime):
    global RUNTIME
    RUNTIME = runtime
    for key, value in runtime.__dict__.items():
        if not key.startswith("__"):
            globals()[key] = value


def get_asset_cleanup_targets():
    return [
        ("apkg", APKG_DIR),
        ("audio", AUDIO_DIR),
        ("csv", CSV_DIR),
        ("voca", VOCA_DIR),
    ]


def count_directory_contents(directory):
    files = 0
    dirs = 0

    try:
        directory = Path(directory)
        if not directory.exists():
            return files, dirs

        for item in directory.iterdir():
            if item.is_dir() and not item.is_symlink():
                dirs += 1
            else:
                files += 1
    except Exception:
        pass

    return files, dirs


def delete_contents_in_directory(directory):
    deleted_files = 0
    deleted_dirs = 0
    failed = []

    directory.mkdir(parents=True, exist_ok=True)

    for item in sorted(directory.iterdir(), key=lambda path: path.name.lower()):
        try:
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
                deleted_dirs += 1
            else:
                item.unlink()
                deleted_files += 1
        except Exception as e:
            failed.append((item, str(e)))

    return deleted_files, deleted_dirs, failed


def draw_asset_cleanup_menu():
    ui_clear_screen()
    ui_title("작업 자료 삭제", "폴더별로 선택 삭제하거나 전체 작업 자료를 삭제합니다.")

    ui_notice("경고", [
        "선택한 폴더 안의 자료를 삭제합니다.",
        "삭제된 파일은 휴지통으로 이동하지 않고 바로 삭제됩니다.",
        "이 작업은 되돌릴 수 없습니다. 반드시 필요한 파일을 백업한 후 진행하십시오.",
    ])

    ui_section("폴더별 삭제")
    targets = get_asset_cleanup_targets()
    for index, (label, directory) in enumerate(targets, start=1):
        files, dirs = count_directory_contents(directory)
        ui_item(f"{index})", label, f"파일 {files}개 / 폴더 {dirs}개 · {directory}")

    total_files = 0
    total_dirs = 0
    for _, directory in targets:
        files, dirs = count_directory_contents(directory)
        total_files += files
        total_dirs += dirs

    ui_section("일괄 삭제")
    ui_item("A)", "apkg / audio / csv / voca 전체 삭제", f"파일 {total_files}개 / 폴더 {total_dirs}개")

    ui_section("이동")
    ui_item("B)", "이전 화면")
    ui_item("M)", "메인 메뉴")
    ui_item("S)", "종료")


def confirm_asset_cleanup(selected_targets, title):
    ui_clear_screen()
    ui_title("작업 자료 삭제 확인", title)

    ui_notice("최종 확인", [
        "정말 삭제할까요?",
        "선택한 작업 폴더의 기존 데이터가 모두 소멸됩니다.",
        "삭제된 파일은 휴지통으로 이동하지 않고 바로 삭제됩니다.",
        "백업하지 않은 자료는 영구적으로 손실될 수 있습니다.",
    ])

    ui_section("삭제 대상")
    total_files = 0
    total_dirs = 0
    for label, directory in selected_targets:
        files, dirs = count_directory_contents(directory)
        total_files += files
        total_dirs += dirs
        ui_item(label, str(directory), f"파일 {files}개 / 폴더 {dirs}개")

    ui_section("요약")
    ui_item("파일", f"{total_files}개")
    ui_item("폴더", f"{total_dirs}개")

    ui_section("확인")
    ui_item("Y)", "삭제합니다")
    ui_item("N)", "취소합니다")

    while True:
        answer = normalize_menu_answer(input("\n정말로 삭제하시겠습니까? > Y/N > "))

        if answer == "Y":
            return True

        if answer in {"N", ""}:
            return False

        say("Y 또는 N으로 입력해주세요.")


def run_asset_cleanup(selected_targets):
    total_files = 0
    total_dirs = 0
    failed_items = []

    for label, directory in selected_targets:
        deleted_files, deleted_dirs, failed = delete_contents_in_directory(directory)
        total_files += deleted_files
        total_dirs += deleted_dirs

        for item, reason in failed:
            failed_items.append((label, item, reason))

    ui_clear_screen()

    if failed_items:
        ui_error("일부 자료를 삭제하지 못했습니다.")
    else:
        ui_completed("삭제되었습니다.")

    ui_section("삭제 결과")
    ui_item("파일", f"{total_files}개")
    ui_item("폴더", f"{total_dirs}개")

    if failed_items:
        ui_section("삭제 실패")
        for label, item, reason in failed_items[:12]:
            ui_write(f"  [{label}] {item.name}")
            for line in _wrap_display(reason, _terminal_width() - 10):
                ui_write("      " + line)
            ui_write("")

        if len(failed_items) > 12:
            ui_write(f"  ... 외 {len(failed_items) - 12}개")

    wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")


def delete_asset_folder_contents():
    targets = get_asset_cleanup_targets()

    while True:
        draw_asset_cleanup_menu()
        answer_raw = ui_prompt("삭제 대상")

        if handle_easter_egg_command(answer_raw):
            continue

        answer = normalize_menu_answer(answer_raw)

        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= len(targets):
                selected = [targets[index - 1]]
                if confirm_asset_cleanup(selected, f"{selected[0][0]} 폴더의 자료를 삭제합니다."):
                    run_asset_cleanup(selected)
                else:
                    ui_clear_screen()
                    ui_completed("삭제하지 않았습니다.")
                    wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
                return

            say("목록에 있는 번호만 입력해주세요.")
            time.sleep(0.8)
            continue

        if answer in {"A", "ALL", "전체", "일괄"}:
            if confirm_asset_cleanup(targets, "apkg / audio / csv / voca 전체 자료를 삭제합니다."):
                run_asset_cleanup(targets)
            else:
                ui_clear_screen()
                ui_completed("삭제하지 않았습니다.")
                wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
            return

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        say("1~4, A, B, M, S 중에서 입력해주세요.")
        time.sleep(0.8)


def get_optional_package_display_targets():
    return [
        ("dev_utility.dpack", DEV_UTILITY_PACK_PATH),
        ("lami.lpack", LAMI_PACK_PATH),
    ]


def get_optional_package_cleanup_targets():
    targets = list(get_optional_package_display_targets())

    if LEGACY_LAMI_PACK_PATH.exists():
        targets.append(("legacy_lami_pack", LEGACY_LAMI_PACK_PATH))

    return targets


def delete_optional_package_files():

    ui_clear_screen()
    ui_title("선택 패키지 삭제", "Developer Utility와 LAMI 선택 패키지를 제거합니다.")

    display_targets = get_optional_package_display_targets()
    cleanup_targets = get_optional_package_cleanup_targets()
    existing_targets = [(label, path) for label, path in cleanup_targets if path.exists()]

    ui_notice("안내", [
        "선택 설치된 dev_utility.dpack과 lami.lpack 파일을 삭제합니다.",
        "일반 AnkiVoice 기능, 설정 파일, 로그, 작업 자료는 삭제하지 않습니다.",
        "선택 패키지가 모두 제거되면 프로그램 표시명은 AnkiVoice로 전환됩니다.",
    ])

    ui_section("삭제 대상")
    for label, path in display_targets:
        ui_kv(label, path, "있음" if path.exists() else "없음")

    if not existing_targets:
        refresh_app_identity()
        ui_completed("삭제할 선택 패키지가 없습니다.")
        ui_section("현재 표시명")
        ui_item("Name", getattr(RUNTIME, "APP_BUILD_LABEL", APP_BUILD_LABEL))
        wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
        return

    ui_section("확인")
    ui_item("Y)", "선택 패키지를 삭제합니다")
    ui_item("N)", "취소합니다")

    while True:
        answer = normalize_menu_answer(input("\n정말로 삭제하시겠습니까? > Y/N > "))

        if answer == "Y":
            break

        if answer in {"N", ""}:
            ui_clear_screen()
            ui_completed("삭제하지 않았습니다.")
            wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
            return

        say("Y 또는 N으로 입력해주세요.")

    deleted = []
    failed = []

    for label, path in existing_targets:
        try:
            path.unlink()
            deleted.append((label, path))
        except Exception as e:
            failed.append((label, path, str(e)))

    if RUNTIME is not None:
        RUNTIME.DEV_UTILITY_MODULE = None
    refresh_app_identity()

    ui_clear_screen()

    if failed:
        ui_error("일부 선택 패키지를 삭제하지 못했습니다.")
    else:
        ui_completed("선택 패키지를 삭제했습니다.")

    ui_section("삭제 결과")
    if deleted:
        for label, path in deleted:
            ui_item(label, "삭제됨", str(path))
    else:
        ui_item("삭제됨", "없음")

    if failed:
        ui_section("삭제 실패")
        for label, path, reason in failed:
            ui_item(label, reason, str(path))

    ui_section("현재 표시명")
    ui_item("Name", getattr(RUNTIME, "APP_BUILD_LABEL", APP_BUILD_LABEL))

    wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
