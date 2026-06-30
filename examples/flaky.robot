*** Settings ***
Documentation    A deterministically flaky test: fails the first attempt,
...              passes on retry. Demonstrates ropayr --retry + flaky detection.
Library          OperatingSystem

*** Variables ***
${FLAG}    %{TMPDIR=/tmp}/ropayr_flaky.flag

*** Test Cases ***
Sometimes Fails
    ${seen}=    Run Keyword And Return Status    File Should Exist    ${FLAG}
    IF    not ${seen}
        Create File    ${FLAG}
        Fail    first attempt fails on purpose
    END
    Remove File    ${FLAG}
    Log    passed on retry
