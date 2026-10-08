"""执行失败回显是否在本案断言的预期内：移植自 InfoTest tests/ist_core/tools/test_anomaly_expected_frame.py
（不依赖真机切片夹具的那几条），钉住 cex_client.device 与 InfoTest batch_tools 同一判据。

夹具是 InfoTest 案 245861784181730661 第 2 轮真日志的切片：该案的测试点就是「设备必须拒绝这条命令」，
设备把拒绝分两行打印，理由行在前、Failed to execute the command 在后。
"""

from __future__ import annotations

from cex_client import device

REJECT_PATTERN = "is in use.*not allowed to add|already in use|cannot be added"
ANOMALY = "Failed to execute the command"

REAL_LOG = """2026-09-03 20:57:03 172.16.35.70 - sends command in config: slb virtual httplist vs3 addlist1 port1
2026-09-03 20:57:03 172.16.35.70 - sends command in config: slb virtual addrlists "addlist1" 172.16.34.70
2026-09-03 20:57:03 #### Success Num 1: successed to find is in use.*not allowed to add in :
2026-09-03 20:57:03 slb virtual addrlists "addlist1" 172.16.34.70
2026-09-03 20:57:03
2026-09-03 20:57:03 The virtual service ip address list is in use. It is not allowed to add another ip to it or delete the ip address list.
2026-09-03 20:57:03 Failed to execute the command
2026-09-03 20:57:03
2026-09-03 20:57:03 APV(config)#
2026-09-03 20:57:04 #######   step5: 客户端尝试访问新添加的IP地址，预期访问失败
2026-09-03 20:57:05 RouterA executes command: ( curl -m 5 http://172.16.34.70:80 ); echo
2026-09-03 20:57:06 curl: (7) Failed to connect to 172.16.34.70 port 80 after 2 ms: No route to host
"""


def test_rejection_asserted_by_the_case_is_not_vacuity_evidence():
    assert device.failure_echo_expected([ANOMALY], [("found", REJECT_PATTERN)], REAL_LOG) is True


def test_line_local_comparison_alone_still_misses_it():
    """没有帧正文时判据只能看那一行，必然落空。"""
    assert device.failure_echo_expected([ANOMALY], [("found", REJECT_PATTERN)], "") is False


def test_repeated_raw_failure_cannot_reuse_the_first_frames_coverage():
    log = REAL_LOG + "\nRouterA# separate-command\nUnrelated failure reason\n" + ANOMALY
    assert not device.failure_echo_expected([ANOMALY, ANOMALY], [("found", REJECT_PATTERN)], log)


def test_framework_annotation_lines_cannot_self_certify():
    """#### … successed to find <pattern> 逐字复读 pattern；它不算设备回显。"""
    log = """2026-09-03 20:57:03 172.16.35.70 - sends command in config: config all tftp
2026-09-03 20:57:03 #### Success Num 1: successed to find OnlyInTheAnnotation in :
2026-09-03 20:57:03 Failed to get the file from tftp server
2026-09-03 20:57:03 Failed to execute the command
"""
    assert device.failure_echo_expected(
        ["Failed to execute the command"], [("found", "OnlyInTheAnnotation")], log) is False


def test_the_668030_vacuous_shape_stays_unexpected():
    """真空真形态：恢复步失败，断言与该帧无关。"""
    log = """2026-09-03 20:57:03 172.16.35.70 - sends command in config: config all tftp 10.0.0.1
2026-09-03 20:57:03 Failed to get the file from tftp server
2026-09-03 20:57:03 Failed to execute the command
2026-09-03 20:57:04 #######   step9: 校验
2026-09-03 20:57:04 172.16.35.70 - sends command in config: show slb virtual
2026-09-03 20:57:04 vs3 is present
"""
    assert device.failure_echo_expected(
        ["Failed to execute the command"], [("found", "vs3 is present")], log) is False


def test_frames_split_on_command_dispatch_and_step_markers():
    frames = device._echo_frames(REAL_LOG)
    heads = [lines[0] for lines, _body in frames if lines]
    assert heads[0].endswith("slb virtual httplist vs3 addlist1 port1")
    assert heads[1].endswith('slb virtual addrlists "addlist1" 172.16.34.70')
    assert heads[2] == "APV(config)#"
    assert heads[3].startswith("#######   step5:")
    assert heads[4].startswith("RouterA executes command:")
    assert frames[2][1].strip() == ""
    reject_frame = frames[1]
    assert any("#### Success Num 1" in ln for ln in reject_frame[0])
    assert "#### Success Num 1" not in reject_frame[1]
    assert "The virtual service ip address list is in use." in reject_frame[1]


def test_frame_body_excludes_the_command_line_itself():
    dispatch_frame = device._echo_frames(REAL_LOG)[0]
    assert dispatch_frame[0][0].endswith("slb virtual httplist vs3 addlist1 port1")
    assert "slb virtual httplist" not in dispatch_frame[1]


def test_host_prompt_rule_does_not_shatter_the_framework_log():
    for line in ("#### Fail Num 1: fail to find case203031754297105910 in: ",
                 "#### Success Num 1: successed to find is in use in :",
                 "#######   step5: 客户端尝试访问",
                 "################# The failed check point num:   1   ####",
                 "The SDNS host does not exist.",
                 "RTNETLINK answers: Cannot assign requested address",
                 ";; SERVER: 172.16.34.70#53(172.16.34.70)"):
        assert device._FRAME_HOST_PROMPT_RE.match(line) is None
    for line in ("RouterA# ip addr delete 1.2.3.4/24 dev ens192", "RouterB$ sudo su", "RouterA#"):
        assert device._FRAME_HOST_PROMPT_RE.match(line)


def test_a_success_summary_of_the_cases_own_pattern_is_expected():
    """负向用例断言的拒绝措辞本身含失败字面：框架的成功摘要逐字复读它，不算新的执行失败
    （InfoTest 2026-09-21 案 203031754291994957）。"""
    summary = "2026-09-21 10:00:00 #### Success Num 1: successed to find: Failed to execute the command"
    assert device.failure_echo_expected(
        [summary], [("found", "Failed to execute the command")], summary) is True
    assert device.failure_echo_expected(
        [summary], [("found", "something else")], summary) is False
