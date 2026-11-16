package com.aharaiq.product.dto;

public record NutritionFactResponse(
        String field,
        Double value,
        String unit,
        String basis) {
}
