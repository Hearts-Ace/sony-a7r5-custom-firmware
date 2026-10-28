"""Bind all final Fn evidence and its executed sources to one final AP."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
CAND = HERE.parent
ROOT = CAND.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(relative):
    return json.loads((CAND / relative).read_text())


def binding(path):
    return dict(path=str(path.relative_to(ROOT)), sha256=digest(path))


def check(evidence, native, fixtures, limits):
    return dict(passed=True,
                evidence=[str((CAND / p).relative_to(ROOT)) for p in evidence],
                native_executed=native, fixtures=fixtures, limits=limits)


def main():
    ap = CAND / "ap/appFw.so"
    ap_sha = digest(ap)
    candidates = read("fn/fn433_candidates.json")
    saves = read("fn/fn433_save_roundtrip.json")
    labels = read("fn/fn433_registration_labels.json")
    activation = read("fn_activation/fn433_activation.json")
    stack = read("fn_activation/fn433_stack_restore.json")
    delta = read("delta433_verified.json")
    templates = read("preservation/generated/templates_manifest.json")
    preservation = read("preservation/verification.json")
    reports = [candidates, saves, labels, activation, stack, delta]
    assert all(r["passed"] and r["AP_sha256"] == ap_sha for r in reports)
    assert candidates["native_validity_cases"] == 156
    assert candidates["native_build_cases"] == 20
    assert all(case["original_items_unchanged"] for row in candidates["rows"] for case in row["builds"])
    assert saves["native_registration_cases"] == saves["native_shadow_roundtrips"] == 96
    for row in saves["rows"]:
        assert len(row["cases"]) == 48
        for case in row["cases"]:
            assert case["function_id"] == case["first_screen_reader_mid"] == "0x635"
            assert case["other_slots_unchanged"]
            expected_pid = (0x7AD if case["kind"] == "still" else 0x7B9) + case["slot"]
            assert case["notification_pids"] == [hex(expected_pid), "0x389"]
            assert case["native_shadow_save"] and case["native_shadow_restore"]
    assert labels["registration_label_cases"] == 4
    for row in labels["rows"]:
        for case in row["cases"]:
            assert case["private_text_dispatch"] == [["name_char", "自定义滤镜"]]
            assert case["private_child_resource"] == "0x2ff4230"
            assert case["creative_look_resource"] == "0x200a2fd"
    assert activation["native_activation_cases"] == 48
    assert activation["native_icon_consumer_cases"] == 8
    assert activation["native_private_return_cases"] == 2
    assert sum(len(row["activations"]) for row in activation["rows"]) == 48
    for row in activation["rows"]:
        for case in row["activations"]:
            assert case["queue_record"] == [0xC2, 0xD9, 0xC2, 0, 1, 0]
            assert case["reader_mid"] == case["selected_pid_3b2"] == "0x635"
        assert row["icons"]["icon"] == "0x21c6410"
        assert row["icons"]["title"] == "自定义滤镜"
        assert row["private_return"]["close_request"] == "0xd9"
        for projection in row["fn_projection"]:
            assert projection["title_text"] == "自定义滤镜"
            assert projection["sprite_resource"] == "0x21c6410"
            assert projection["sprite_resource_enabled"]
    assert stack["cases"] == len(stack["rows"]) == 6
    for case in stack["rows"]:
        assert case["push_count"] == case["pop_count"] == 1
        assert case["restored_screen"] == "0xc2"
        assert case["fn_presenter_reconstructed"] and case["lower_stack_unchanged"] and case["callee_saved"]
        projection = case["restored_presenter_native_projection"]
        assert projection["title_text"] == "自定义滤镜"
        assert projection["sprite_resource"] == "0x21c6410" and projection["sprite_resource_enabled"]
    assert delta["native_Fn_candidate_delta_verified"]
    assert delta["menu_source_only_two_icon_constants"] and delta["other_compiler_objects_exact432"]
    assert delta["Fn_patch"]["changed_bytes"] == 41
    assert templates["passed"] and preservation["passed"]
    assert templates["total_ranges_each"] == 13 and templates["count"] == 12
    assert not templates["personalized_partition_embedded"]
    assert preservation["patched_templates_BK4_checksums_and_native_ranges_verified"]
    # Replace the preliminary pre-icon candidate ledger with the exact final
    # build's source/patched identities. The underlying 41-byte table patch
    # itself is unchanged.
    (HERE / "data_patch_plan.json").write_text(json.dumps(delta["Fn_patch"], indent=2) + "\n")

    candidate_evidence = ["fn/fn433_candidates.json", "delta433_verified.json"]
    save_evidence = ["fn/fn433_save_roundtrip.json"]
    activate_evidence = ["fn_activation/fn433_activation.json"]
    return_evidence = activate_evidence + ["fn_activation/fn433_stack_restore.json"]
    name_evidence = ["fn/fn433_registration_labels.json"] + return_evidence
    checks = dict(
        registration_candidate=check(candidate_evidence,
            ["1bc8c58 generic dispatcher; 1bdd6f8 native Fn builder; 1bd8d9c mode gate; 1bd912c private descriptor lookup: 156 validity + 20 builder cases"],
            candidates["limits"][1:3], ["Physical Fn customization LCD and shooting mode timing remain untested."]),
        native_registration_setter=check(save_evidence,
            ["21e45c8 complete native save handler and original target switch; 21e40f0/21e41dc setters; 21e40bc/21e41a8 notification destructors: 96 cases"],
            saves["service_fixtures"], ["Property observer/backend and physical nonvolatile commit are fixtures."]),
        saved_slot_roundtrip=check(save_evidence,
            ["All 24 native per-slot shadow save/restore helpers and 216eb9c first-screen reader: 96 roundtrips; all values restore MID635 and unrelated slots stay intact"],
            saves["service_fixtures"], ["RAM backup shadow is verified; physical BKID commit, eMMC and cold boot are not executed."]),
        still_movie_activation=check(activate_evidence,
            ["216eb9c reads all 12 still and 12 movie slots at two PIE bases; 1a5de30 Enter dispatcher and 216f2d8 run: 48 cases"],
            activation["limits"][1:3], ["Focused current selection is copied to genuine PID3B2 after reading the slot; focus navigation/button hardware is outside this replay."]),
        fn_invocation_enters_private_page=check(activate_evidence,
            ["1a5de30 ->216f2d8 ->1bd70d8/1bdc3d0 ->1bd5780/1bd59f0 ->216ea14 ->1d15b50/1d15cfc queues C2/D9; compiled private controller factory is selected"],
            activation["limits"][2:4], ["Native queue write and compiled factory dispatch are exercised separately; actual UI event-loop dispatch and original constructor body are not executed."]),
        fn_name_bridge=check(name_evidence,
            labels["native_executed"] + ["2170734 Fn first-screen title producer and existing resource bridge; same-VM restored presenter title projection after native pop"],
            labels["fixtures"] + activation["limits"][4:], labels["limits"] + ["Physical LCD glyphs, truncation and GUI timing remain untested."]),
        native_return_path=check(return_evidence,
            ["Compiled private close dispatcher ->1bd55fc committed-value lookup ->1d15798 close request; 1ec5304/1ec51f4/1ec557c native push/pop restores C2, 6 lower-stack cases; restored presenter pointer then executes native title/tile projection in same VM"],
            activation["limits"][3:4] + stack["limits"][2:4], stack["limits"][4:]),
        original_creative_look_preserved=check(candidate_evidence + ["fn/fn433_registration_labels.json"],
            ["Native Fn candidate builder preserves every original item/order/auxiliary word; ID1f2 still maps to MID1e6; real original Creative Look title resolver returns0200a2fd"],
            ["Other menus' product availability and runtime-dependent titles are fixtures; original Creative Look and private title resolvers execute."],
            ["No replacement of the original Creative Look menu or automatic Fn assignment is introduced."]),
        fn_icon_reuses_creative_look=check(return_evidence + ["delta433_verified.json"],
            ["Private descriptor+0c/+60 and original Creative Look descriptor+0c equal021c6410; native 1bd5630/1bd642c getters; 20d34f8/20d1e54 consumers; 21705a8 Fn tile ->183c85c renderer ->183c138 sprite resource writer"],
            activation["limits"][4:] + stack["limits"][3:4], ["Sprite resource ID/enable bit are verified; physical icon rendering is untested."]))

    receipt_paths = ["fn/fn433_candidates.json", "fn/fn433_save_roundtrip.json",
                     "fn/fn433_registration_labels.json", "fn_activation/fn433_activation.json",
                     "fn_activation/fn433_stack_restore.json", "delta433_verified.json",
                     "preservation/verification.json", "preservation/generated/templates_manifest.json"]
    source_paths = [
        HERE / "patch_fn433.py", HERE / "replay_fn433.py", HERE / "replay_fn_save433.py",
        HERE / "replay_fn_labels433.py", HERE / "finalize_fn433.py", HERE / "README.md",
        HERE / "data_patch_plan.json", CAND / "fn_activation/replay_activation433.py",
        CAND / "fn_activation/replay_stack433.py", CAND / "fn_activation/README.md",
        CAND / "fn_activation/frozen_manifest.json", CAND / "replay_main_menu425.py",
        CAND / "import/module_audit.json", CAND / "menu_research/r5_filter_menu423.c",
        CAND / "menu_research/r5_filter_menu423.h", CAND / "menu_research/r5_filter_renderer423.c",
        CAND / "menu_research/r5_filter_renderer423.S", CAND / "import/r5_filter_names423.c",
        ROOT / "analysis/r5_custom_filter423_20261023/menu_research/read_menu.py",
        ROOT / "analysis/r5_custom_filter423_20261023/import/module_audit.json",
    ]
    for report, script in [(candidates, HERE / "replay_fn433.py"),
                           (saves, HERE / "replay_fn_save433.py"),
                           (labels, HERE / "replay_fn_labels433.py"),
                           (activation, CAND / "fn_activation/replay_activation433.py"),
                           (stack, CAND / "fn_activation/replay_stack433.py")]:
        assert report["script_sha256"] == digest(script), script
    report = dict(
        schema="r5-fn433-final-native-evidence/1", passed=True, AP_sha256=ap_sha,
        checks=checks, receipts=[binding(CAND / p) for p in receipt_paths],
        source_bindings=[binding(p) for p in source_paths],
        manual_assignment_required=True, default_fn_slots_modified=False,
        assignment_path="Fn菜单设置 → 颜色/色调 → 自定义滤镜",
        default_slot_evidence="AP delta is confined to the candidate table and two icon initializer constants; all other compiled objects match4.32. All12 templates are independently confined to13 color ranges plus BK4 checksums, without personalized settings.",
        camera_io=False, physical_display_tested=False, cold_boot_tested=False,
        limits=["Host A64 replay establishes the declared native instruction/data paths with named fixtures.",
                "Camera Fn registration persistence, actual UI timing/fonts/icons, cold boot and photography remain for physical acceptance."])
    out = HERE / "fn433_verified.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(passed=True, AP_sha256=ap_sha, checks=list(checks),
                          receipts=len(report["receipts"]), sources=len(source_paths), output=str(out))))


if __name__ == "__main__":
    main()
