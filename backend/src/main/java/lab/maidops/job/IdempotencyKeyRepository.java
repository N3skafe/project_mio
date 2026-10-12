package lab.maidops.job;

import java.util.Optional;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface IdempotencyKeyRepository extends JpaRepository<IdempotencyKeyEntity, String> {
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select key from IdempotencyKeyEntity key where key.keyText = :keyText")
    Optional<IdempotencyKeyEntity> lockByKey(@Param("keyText") String keyText);
}
