package lab.maidops.errorcase;

import java.util.regex.Pattern;

/**
 * 워커 mask_secrets와 같은 형태만 가린다.
 * 저장된 로그를 다시 가리지 않고, 가져오기 원문을 저장하기 전에만 쓴다.
 */
public final class SecretMasker {
    private static final Pattern URI_USERINFO = Pattern.compile(
            "(?i)([a-z][a-z0-9+.-]*://[^/\\s:@]*:)([^@\\s]+)@");
    private static final Pattern ASSIGNMENT = Pattern.compile(
            "(?i)\\b(password|passwd|secret|api[_-]?key|token)\\b(\\s*[=:]\\s*)(\\S+)");
    private static final Pattern BEARER = Pattern.compile("(?i)\\bBearer\\s+\\S+");

    private SecretMasker() {
    }

    public static String mask(String text) {
        String masked = URI_USERINFO.matcher(text).replaceAll("$1[REDACTED]@");
        masked = ASSIGNMENT.matcher(masked).replaceAll("$1$2[REDACTED]");
        return BEARER.matcher(masked).replaceAll("Bearer [REDACTED]");
    }
}
