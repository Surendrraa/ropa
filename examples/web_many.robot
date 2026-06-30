*** Settings ***
Library    Browser

*** Test Cases ***
Case 00
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    Add Cookie    k    v0    url=https://example.com
    ${c}=    Get Cookies
    Length Should Be    ${c}    1
    Sleep    0.2s

Case 01
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    Add Cookie    k    v1    url=https://example.com
    ${c}=    Get Cookies
    Length Should Be    ${c}    1
    Sleep    0.2s

Case 02
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    Add Cookie    k    v2    url=https://example.com
    ${c}=    Get Cookies
    Length Should Be    ${c}    1
    Sleep    0.2s

Case 03
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    Add Cookie    k    v3    url=https://example.com
    ${c}=    Get Cookies
    Length Should Be    ${c}    1
    Sleep    0.2s

Case 04
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    Add Cookie    k    v4    url=https://example.com
    ${c}=    Get Cookies
    Length Should Be    ${c}    1
    Sleep    0.2s

Case 05
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    Add Cookie    k    v5    url=https://example.com
    ${c}=    Get Cookies
    Length Should Be    ${c}    1
    Sleep    0.2s

Case 06
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    Add Cookie    k    v6    url=https://example.com
    ${c}=    Get Cookies
    Length Should Be    ${c}    1
    Sleep    0.2s

Case 07
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    Add Cookie    k    v7    url=https://example.com
    ${c}=    Get Cookies
    Length Should Be    ${c}    1
    Sleep    0.2s

Case 08
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    Add Cookie    k    v8    url=https://example.com
    ${c}=    Get Cookies
    Length Should Be    ${c}    1
    Sleep    0.2s

Case 09
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    Add Cookie    k    v9    url=https://example.com
    ${c}=    Get Cookies
    Length Should Be    ${c}    1
    Sleep    0.2s
