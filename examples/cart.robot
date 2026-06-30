*** Settings ***
Documentation    Second sample suite to show cross-suite parallelism.

*** Test Cases ***
Add Item
    Log    add
    Sleep    0.4s

Remove Item
    Log    remove
    Sleep    0.3s

Checkout
    Log    checkout
    Sleep    0.9s
