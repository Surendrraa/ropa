*** Settings ***
Documentation    Browser suite — unmodified New Browser/New Context/New Page.
...              Under `ropa --browser chromium` these attach to the SHARED
...              browser, each test in its own isolated context.
Library          Browser

*** Test Cases ***
Login Session Is Isolated
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    Add Cookie    session    alice    url=https://example.com
    ${cookies}=    Get Cookies
    Length Should Be    ${cookies}    1
    Sleep    0.3s

Search Session Is Isolated
    New Browser    chromium    headless=True
    New Context
    New Page    about:blank
    ${cookies}=    Get Cookies
    Length Should Be    ${cookies}    0
    Add Cookie    session    bob    url=https://example.com
    Sleep    0.5s
