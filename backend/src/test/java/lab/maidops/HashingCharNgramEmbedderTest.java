package lab.maidops;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

import lab.maidops.search.HashingCharNgramEmbedder;
import org.junit.jupiter.api.Test;

class HashingCharNgramEmbedderTest {
    @Test
    void matchesTheTrainerHashFingerprint() {
        double[] vector = HashingCharNgramEmbedder.embed("Connection to localhost:5432 refused");
        assertThat(vector).hasSize(256);
        assertThat(HashingCharNgramEmbedder.cosine(vector, vector)).isCloseTo(1.0, within(1e-6));
        assertThat(vector[1]).isCloseTo(-0.09245, within(1e-4));
        assertThat(vector[7]).isCloseTo(0.09245, within(1e-4));
        assertThat(vector[8]).isCloseTo(0.1849, within(1e-4));
        double[] similar = HashingCharNgramEmbedder.embed(
                "org.postgresql.util.PSQLException: Connection to localhost:5432 refused");
        double[] unrelated = HashingCharNgramEmbedder.embed("disk quota exceeded while writing the artifact");
        assertThat(HashingCharNgramEmbedder.cosine(vector, similar)).isGreaterThan(0.35);
        assertThat(HashingCharNgramEmbedder.cosine(vector, unrelated)).isLessThan(0.35);
    }
}
