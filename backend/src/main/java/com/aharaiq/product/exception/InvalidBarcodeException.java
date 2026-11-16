package com.aharaiq.product.exception;

public class InvalidBarcodeException extends RuntimeException {
    public InvalidBarcodeException(String barcode) {
        super("Barcode must contain 8 to 14 digits: " + barcode);
    }
}
