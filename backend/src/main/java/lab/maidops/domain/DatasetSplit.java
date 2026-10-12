package lab.maidops.domain;

public enum DatasetSplit {
    TRAIN,
    VAL,
    TEST;

    public int holdoutRank() {
        return switch (this) {
            case TRAIN -> 1;
            case VAL -> 2;
            case TEST -> 3;
        };
    }
}
