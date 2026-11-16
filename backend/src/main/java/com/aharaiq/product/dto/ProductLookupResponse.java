package com.aharaiq.product.dto;

import java.util.List;

public record ProductLookupResponse(
        boolean found,
        String barcode,
        String name,
        String brand,
        String category,
        String imageUrl,
        String ingredients,
        List<NutritionFactResponse> nutritionFacts,
        List<String> missingFields,
        String source) {
}
