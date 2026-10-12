package lab.maidops.errorcase;

import java.time.Instant;
import java.util.Collection;
import java.util.List;

import lab.maidops.domain.ReviewStatus;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ErrorCaseRepository extends JpaRepository<ErrorCaseEntity, String> {
    @Query("""
            select errorCase from ErrorCaseEntity errorCase
            order by errorCase.createdAt asc, errorCase.id asc
            limit :limit
            """)
    List<ErrorCaseEntity> firstPage(@Param("limit") int limit);

    @Query("""
            select errorCase from ErrorCaseEntity errorCase
            where errorCase.createdAt > :createdAt
                or (errorCase.createdAt = :createdAt and errorCase.id > :id)
            order by errorCase.createdAt asc, errorCase.id asc
            limit :limit
            """)
    List<ErrorCaseEntity> pageAfter(
            @Param("createdAt") Instant createdAt,
            @Param("id") String id,
            @Param("limit") int limit);

    @Query("""
            select errorCase from ErrorCaseEntity errorCase
            where lower(errorCase.id) like lower(concat('%', :query, '%')) escape '\\'
               or lower(errorCase.jobId) like lower(concat('%', :query, '%')) escape '\\'
               or lower(errorCase.rawText) like lower(concat('%', :query, '%')) escape '\\'
            order by errorCase.createdAt asc
            """)
    List<ErrorCaseEntity> search(@Param("query") String query);

    List<ErrorCaseEntity> findByReviewStatusInOrderByCreatedAtAscIdAsc(Collection<ReviewStatus> statuses);

    long countByReviewStatus(ReviewStatus status);
}
