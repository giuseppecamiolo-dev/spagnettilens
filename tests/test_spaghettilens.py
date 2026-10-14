import pytest
from spaghettilens import get_prompt_for_action

def test_get_prompt_for_action_document_php():
    code = "<?php echo 'hello'; ?>"
    prompt = get_prompt_for_action("document", code, ".php")
    assert "You are a Senior Backend Engineer specializing in legacy PHP modernization." in prompt
    assert "Add comprehensive PHPDoc or POD comments" in prompt
    assert "Code:\n" + code in prompt

def test_get_prompt_for_action_document_perl():
    code = "print 'hello';"
    prompt = get_prompt_for_action("document", code, ".pl")
    assert "You are a Senior Backend Engineer specializing in legacy Perl modernization." in prompt
    assert "Add comprehensive PHPDoc or POD comments" in prompt
    assert "Code:\n" + code in prompt

def test_get_prompt_for_action_security_php():
    code = "<?php mysql_query('SELECT * FROM users'); ?>"
    prompt = get_prompt_for_action("security", code, ".php")
    assert "You are a Senior Backend Engineer specializing in legacy PHP modernization." in prompt
    assert "Analyze this legacy PHP code for security vulnerabilities" in prompt
    assert "Code:\n" + code in prompt

def test_get_prompt_for_action_security_perl():
    code = "system($user_input);"
    prompt = get_prompt_for_action("security", code, ".pl")
    assert "You are a Senior Backend Engineer specializing in legacy Perl modernization." in prompt
    assert "Analyze this legacy Perl code for security vulnerabilities" in prompt
    assert "Code:\n" + code in prompt

def test_get_prompt_for_action_refactor_php():
    code = "<?php include 'db.php'; ?>"
    prompt = get_prompt_for_action("refactor", code, ".php")
    assert "You are a Senior Backend Engineer specializing in legacy PHP modernization." in prompt
    assert "Refactor this legacy PHP code into a modern, secure format." in prompt
    assert "Code:\n" + code in prompt

def test_get_prompt_for_action_refactor_perl():
    code = "use CGI;"
    prompt = get_prompt_for_action("refactor", code, ".pl")
    assert "You are a Senior Backend Engineer specializing in legacy Perl modernization." in prompt
    assert "Refactor this legacy Perl code into a modern, secure format." in prompt
    assert "Code:\n" + code in prompt

def test_get_prompt_for_action_invalid_action():
    code = "<?php ?>"
    prompt = get_prompt_for_action("invalid_action", code, ".php")
    # Should fallback to security action
    assert "You are a Senior Backend Engineer specializing in legacy PHP modernization." in prompt
    assert "Analyze this legacy PHP code for security vulnerabilities" in prompt
    assert "Code:\n" + code in prompt

def test_get_prompt_for_action_unknown_extension():
    code = "unknown"
    # An unknown extension should fallback to PHP based on the code:
    # language = "Perl" if extension == ".pl" else "PHP"
    prompt = get_prompt_for_action("document", code, ".txt")
    assert "You are a Senior Backend Engineer specializing in legacy PHP modernization." in prompt
    assert "Code:\n" + code in prompt
