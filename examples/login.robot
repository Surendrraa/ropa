*** Settings ***
Documentation    Sample suite to exercise ropa (no browser needed).

*** Test Cases ***
Fast Check
    Log    quick test
    Sleep    0.2s

Medium Check
    Log    medium test
    Sleep    0.6s

Slow Check
    Log    slow test
    Sleep    1.2s
