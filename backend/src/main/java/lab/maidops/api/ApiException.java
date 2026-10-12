package lab.maidops.api;

public class ApiException extends RuntimeException {
    private final int status;
    private final String code;
    private final String example;

    public ApiException(int status, String code, String message, String example) {
        super(message);
        this.status = status;
        this.code = code;
        this.example = example == null ? "" : example;
    }

    public int status() {
        return status;
    }

    public ApiError toBody() {
        return new ApiError(code, getMessage(), example);
    }
}
