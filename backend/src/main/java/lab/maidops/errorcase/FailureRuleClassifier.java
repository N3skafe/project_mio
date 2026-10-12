package lab.maidops.errorcase;

import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import lab.maidops.domain.ErrorLabel;

/**
 * 실패 로그의 규칙 기반 초안.
 *
 * 키워드 목록과 우선순위는 TUI의 rules.py와 같게 유지한다.
 * 점수를 만들지 않으며, 일치 키워드는 정답 확률이 아니다.
 */
public final class FailureRuleClassifier {
    public static final String RULE_VERSION = "rules-1";

    private static final Pattern STATUS_CODE = Pattern.compile("(?<!\\d)(401|403)(?!\\d)");

    private static final List<Rule> RULES = List.of(
            new Rule(ErrorLabel.AUTH_PERMISSION, List.of(
                    "permission denied",
                    "access denied",
                    "unauthorized",
                    "authentication failed",
                    "not authorized",
                    "forbidden",
                    "eacces")),
            new Rule(ErrorLabel.DB_CONNECTION, List.of(
                    "postgresql",
                    "postgres",
                    ":5432",
                    "sqlstate",
                    "jdbc",
                    "database")),
            new Rule(ErrorLabel.INPUT_VALIDATION, List.of(
                    "invalid input",
                    "required field",
                    "illegal argument",
                    "missing required",
                    "bad request",
                    "입력 검증",
                    "validation")),
            new Rule(ErrorLabel.EXTERNAL_NETWORK, List.of(
                    "temporary failure in name resolution",
                    "name or service not known",
                    "name resolution",
                    "getaddrinfo",
                    "network is unreachable",
                    "no route to host",
                    "connection timed out",
                    "connection refused",
                    "timed out",
                    "timeout",
                    "dns")));

    private FailureRuleClassifier() {
    }

    public static RuleDraft classify(String text) {
        String haystack = text == null ? "" : text.toLowerCase(Locale.ROOT);
        Matcher statusCode = STATUS_CODE.matcher(haystack);
        if (statusCode.find()) {
            return new RuleDraft(ErrorLabel.AUTH_PERMISSION, RULE_VERSION, statusCode.group(1));
        }
        for (Rule rule : RULES) {
            for (String keyword : rule.keywords()) {
                if (haystack.contains(keyword.toLowerCase(Locale.ROOT))) {
                    return new RuleDraft(rule.label(), RULE_VERSION, keyword);
                }
            }
        }
        return new RuleDraft(ErrorLabel.OTHER, RULE_VERSION, null);
    }

    public record RuleDraft(ErrorLabel label, String ruleVersion, String matchedKeyword) {
    }

    private record Rule(ErrorLabel label, List<String> keywords) {
    }
}
