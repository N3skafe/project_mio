package lab.maidops;

import static org.assertj.core.api.Assertions.assertThat;

import lab.maidops.domain.ErrorLabel;
import lab.maidops.errorcase.FailureRuleClassifier;
import lab.maidops.errorcase.FailureRuleClassifier.RuleDraft;
import org.junit.jupiter.api.Test;

class FailureRuleClassifierTest {
    @Test
    void eachLabelComesFromTheMatchingKeyword() {
        assertDraft("permission denied for user", ErrorLabel.AUTH_PERMISSION, "permission denied");
        assertDraft("status 403 from the api", ErrorLabel.AUTH_PERMISSION, "403");
        assertDraft(
                "org.postgresql.util.PSQLException: Connection to localhost:5432 refused",
                ErrorLabel.DB_CONNECTION,
                "postgresql");
        assertDraft(
                "Validation failed: required field email is missing",
                ErrorLabel.INPUT_VALIDATION,
                "required field");
        assertDraft(
                "Temporary failure in name resolution while calling https://api.example.invalid",
                ErrorLabel.EXTERNAL_NETWORK,
                "temporary failure in name resolution");
        RuleDraft other = FailureRuleClassifier.classify("boom");
        assertThat(other.label()).isEqualTo(ErrorLabel.OTHER);
        assertThat(other.ruleVersion()).isEqualTo(FailureRuleClassifier.RULE_VERSION);
        assertThat(other.matchedKeyword()).isNull();
    }

    @Test
    void earlierCategoryWinsAndDigitsInsideNumbersDoNotMatch() {
        RuleDraft mixed = FailureRuleClassifier.classify("permission denied while opening the database");
        assertThat(mixed.label()).isEqualTo(ErrorLabel.AUTH_PERMISSION);
        assertThat(mixed.matchedKeyword()).isEqualTo("permission denied");
        RuleDraft digits = FailureRuleClassifier.classify("code 14013 boom");
        assertThat(digits.label()).isEqualTo(ErrorLabel.OTHER);
        assertThat(digits.matchedKeyword()).isNull();
    }

    private static void assertDraft(String text, ErrorLabel label, String keyword) {
        RuleDraft draft = FailureRuleClassifier.classify(text);
        assertThat(draft.label()).isEqualTo(label);
        assertThat(draft.ruleVersion()).isEqualTo("rules-1");
        assertThat(draft.matchedKeyword()).isEqualTo(keyword);
    }
}
