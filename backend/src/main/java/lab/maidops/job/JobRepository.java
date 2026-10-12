package lab.maidops.job;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface JobRepository extends JpaRepository<JobEntity, String> {
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select job from JobEntity job where job.id = :id")
    Optional<JobEntity> findLockedById(@Param("id") String id);

    @Query("""
            select job from JobEntity job
            order by job.createdAt asc, job.id asc
            limit :limit
            """)
    List<JobEntity> firstPage(@Param("limit") int limit);

    @Query("""
            select job from JobEntity job
            where job.createdAt > :createdAt or (job.createdAt = :createdAt and job.id > :id)
            order by job.createdAt asc, job.id asc
            limit :limit
            """)
    List<JobEntity> pageAfter(
            @Param("createdAt") Instant createdAt,
            @Param("id") String id,
            @Param("limit") int limit);

    @Query("""
            select job from JobEntity job
            where lower(job.id) like lower(concat('%', :query, '%')) escape '\\'
               or lower(job.projectId) like lower(concat('%', :query, '%')) escape '\\'
               or lower(job.taskId) like lower(concat('%', :query, '%')) escape '\\'
            order by job.createdAt asc, job.id asc
            """)
    List<JobEntity> search(@Param("query") String query);

    @Query("""
            select job from JobEntity job
            where job.status in (lab.maidops.domain.JobStatus.RUNNING, lab.maidops.domain.JobStatus.CANCEL_REQUESTED)
              and job.leaseExpiresAt is not null
              and job.leaseExpiresAt < :now
            """)
    List<JobEntity> findExpired(@Param("now") Instant now);
}
