import unittest
from spaghettilensOllam import get_prompt_for_action

class TestSpaghettilensOllam(unittest.TestCase):
    def test_get_prompt_for_action_document_perl(self):
        code = "print 'Hello';"
        extension = ".pl"
        action = "document"

        prompt = get_prompt_for_action(action, code, extension)

        self.assertIn("Senior Backend Engineer specializing in legacy Perl modernization", prompt)
        self.assertIn("Add comprehensive PHPDoc or POD comments", prompt)
        self.assertIn("Code:\nprint 'Hello';", prompt)

    def test_get_prompt_for_action_security_php(self):
        code = "echo 'Hello';"
        extension = ".php"
        action = "security"

        prompt = get_prompt_for_action(action, code, extension)

        self.assertIn("Senior Backend Engineer specializing in legacy PHP modernization", prompt)
        self.assertIn("Analyze this legacy PHP code for security vulnerabilities", prompt)
        self.assertIn("Code:\necho 'Hello';", prompt)

    def test_get_prompt_for_action_refactor_perl(self):
        code = "print 'Hello';"
        extension = ".pl"
        action = "refactor"

        prompt = get_prompt_for_action(action, code, extension)

        self.assertIn("Senior Backend Engineer specializing in legacy Perl modernization", prompt)
        self.assertIn("Refactor this legacy Perl code into a modern, secure format", prompt)
        self.assertIn("Code:\nprint 'Hello';", prompt)

    def test_get_prompt_for_action_unknown_action_defaults_to_security(self):
        code = "echo 'Hello';"
        extension = ".php"
        action = "unknown_action"

        prompt = get_prompt_for_action(action, code, extension)

        self.assertIn("Senior Backend Engineer specializing in legacy PHP modernization", prompt)
        self.assertIn("Analyze this legacy PHP code for security vulnerabilities", prompt)
        self.assertIn("Code:\necho 'Hello';", prompt)

    def test_get_prompt_for_action_unknown_extension_defaults_to_php(self):
        code = "echo 'Hello';"
        extension = ".xyz"
        action = "document"

        prompt = get_prompt_for_action(action, code, extension)

        self.assertIn("Senior Backend Engineer specializing in legacy PHP modernization", prompt)
        self.assertIn("Add comprehensive PHPDoc or POD comments", prompt)
        self.assertIn("Code:\necho 'Hello';", prompt)

if __name__ == '__main__':
    unittest.main()
