import pytest
from spaghettilensNPU import get_prompt_for_action

def test_get_prompt_for_action_document_perl():
    code = "print 'hello';"
    action = "document"
    extension = ".pl"

    prompt = get_prompt_for_action(action, code, extension)

    assert "Perl" in prompt
    assert "Add comprehensive PHPDoc or POD comments" in prompt
    assert code in prompt

def test_get_prompt_for_action_security_php():
    code = "echo 'hello';"
    action = "security"
    extension = ".php"

    prompt = get_prompt_for_action(action, code, extension)

    assert "PHP" in prompt
    assert "Analyze this legacy PHP code for security vulnerabilities" in prompt
    assert code in prompt

def test_get_prompt_for_action_refactor_perl():
    code = "my $var = 1;"
    action = "refactor"
    extension = ".pl"

    prompt = get_prompt_for_action(action, code, extension)

    assert "Perl" in prompt
    assert "Refactor this legacy Perl code into a modern, secure format" in prompt
    assert code in prompt

def test_get_prompt_for_action_invalid_action_defaults_to_security():
    code = "echo 'hello';"
    action = "invalid_action"
    extension = ".php"

    prompt = get_prompt_for_action(action, code, extension)

    # Defaults to security
    assert "PHP" in prompt
    assert "Analyze this legacy PHP code for security vulnerabilities" in prompt
    assert code in prompt

def test_get_prompt_for_action_unrecognized_extension_defaults_to_php():
    code = "def hello(): pass"
    action = "document"
    extension = ".py"

    prompt = get_prompt_for_action(action, code, extension)

    # language defaults to PHP if not .pl
    assert "PHP" in prompt
    assert "Add comprehensive PHPDoc or POD comments" in prompt
    assert code in prompt
