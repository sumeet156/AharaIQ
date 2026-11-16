package com.aharaiq.exception;

import com.aharaiq.product.exception.InvalidBarcodeException;
import com.aharaiq.product.exception.ProductLookupException;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler(InvalidBarcodeException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Map<String, String> invalidBarcode(InvalidBarcodeException exception) {
        return Map.of("error", "invalid_barcode", "message", exception.getMessage());
    }

    @ExceptionHandler(ProductLookupException.class)
    @ResponseStatus(HttpStatus.BAD_GATEWAY)
    public Map<String, String> lookupFailure(ProductLookupException exception) {
        return Map.of("error", "external_lookup_failed", "message", exception.getMessage());
    }
}
