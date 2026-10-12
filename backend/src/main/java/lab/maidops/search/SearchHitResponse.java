package lab.maidops.search;

import lab.maidops.domain.DataOrigin;
import lab.maidops.domain.SearchKind;

public record SearchHitResponse(SearchKind kind, DataOrigin origin, String title, String excerpt) {
}
