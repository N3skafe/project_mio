package lab.maidops.api;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;

public final class CursorCodec {
    private CursorCodec() {
    }

    public record Cursor(Instant createdAt, String id) {
    }

    public static String encode(Instant createdAt, String id) {
        String raw = createdAt.toString() + "|" + id;
        return Base64.getUrlEncoder().withoutPadding().encodeToString(raw.getBytes(StandardCharsets.UTF_8));
    }

    public static Cursor decode(String cursor) {
        if (cursor == null || cursor.isBlank()) {
            return null;
        }
        try {
            String raw = new String(Base64.getUrlDecoder().decode(cursor), StandardCharsets.UTF_8);
            int split = raw.lastIndexOf('|');
            if (split <= 0 || split == raw.length() - 1) {
                throw new IllegalArgumentException("split");
            }
            Instant createdAt = Instant.parse(raw.substring(0, split));
            String id = raw.substring(split + 1);
            if (id.isBlank() || id.length() > 64) {
                throw new IllegalArgumentException("id");
            }
            return new Cursor(createdAt, id);
        } catch (RuntimeException exception) {
            throw new ApiException(400, "VALIDATION", "cursor가 올바르지 않습니다.", "");
        }
    }
}
