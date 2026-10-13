package lab.maidops.lab;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;

/**
 * 테스트 분할 원문의 지문. 학습기가 보낸 평가가 이 실행의 테스트 사례를 가리키는지 맞춘다.
 * 체크포인트를 열었다는 증거는 아니다.
 */
public final class EvaluationFingerprint {
    public record Row(String id, String label, String rawText) {
    }

    private EvaluationFingerprint() {
    }

    public static String of(List<Row> rows) {
        String joined = rows.stream()
                .sorted(Comparator.comparing(Row::id))
                .map(row -> row.id() + "|" + row.label() + "|" + sha256(row.rawText() == null ? "" : row.rawText()))
                .reduce((left, right) -> left + "\n" + right)
                .orElse("");
        return sha256(joined);
    }

    public static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256을 사용할 수 없습니다.", exception);
        }
    }
}
