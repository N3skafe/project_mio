package lab.maidops.search;

import java.util.List;

public record SimilarSearchResponse(
        String embeddingId,
        String similarityNote,
        String answer,
        List<SimilarHitResponse> hits) {
}
