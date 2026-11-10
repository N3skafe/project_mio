package lab.maidops.search;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;

/**
 * trainer의 hashing-char-ngram-v1과 같은 고정 해시.
 * 파라미터를 학습하지 않고 파일을 받지 않는다.
 */
public final class HashingCharNgramEmbedder {
    public static final String EMBEDDING_ID = "hashing-char-ngram-v1";
    public static final int DIMENSION = 256;
    public static final String SIMILARITY_NOTE =
            "유사도는 hashing-char-ngram-v1 코사인입니다. 정답 확률이 아닙니다.";

    private HashingCharNgramEmbedder() {
    }

    public static double[] embed(String text) {
        double[] vector = new double[DIMENSION];
        String folded = " " + text.toLowerCase(Locale.ROOT).trim().replaceAll("\\s+", " ") + " ";
        MessageDigest digest = sha256();
        for (int width = 3; width <= 5; width++) {
            if (folded.length() < width) {
                continue;
            }
            for (int start = 0; start <= folded.length() - width; start++) {
                byte[] hash = digest.digest(folded.substring(start, start + width).getBytes(StandardCharsets.UTF_8));
                int bucket = (int) (unsignedInt(hash) % DIMENSION);
                double sign = (hash[4] & 0xff) % 2 == 0 ? 1.0 : -1.0;
                vector[bucket] += sign;
            }
        }
        double norm = 0.0;
        for (double value : vector) {
            norm += value * value;
        }
        norm = Math.sqrt(norm);
        if (norm > 0.0) {
            for (int index = 0; index < vector.length; index++) {
                vector[index] /= norm;
            }
        }
        return vector;
    }

    public static double cosine(double[] left, double[] right) {
        double sum = 0.0;
        for (int index = 0; index < DIMENSION; index++) {
            sum += left[index] * right[index];
        }
        return sum;
    }

    private static long unsignedInt(byte[] hash) {
        return (hash[0] & 0xffL)
                | ((hash[1] & 0xffL) << 8)
                | ((hash[2] & 0xffL) << 16)
                | ((hash[3] & 0xffL) << 24);
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256을 사용할 수 없습니다.", exception);
        }
    }
}
