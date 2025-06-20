If you want to apply the same resolution to multiple models:
- Go to General Settings > Attachment Resize.
- In the Attachment Image Resize Models field, enter the technical names of the models
  you want to resize attachment images for (e.g., res.partner, product.template).
- In the same section, set the Attachment Image Max Resolution to define a default
  resolution that applies to the listed models.

Alternatively, to define a custom resolution for a specific model:
- Go to Technical > Models, select a model, and set the
  Attachment Image Max Resolution field.

Priority Order
- If a model has a custom resolution defined in its Attachment Image Max Resolution
  field, that value takes precedence.
- If not, and the model is listed in the Attachment Image Resize Models setting, the
  resolution configured in Settings is applied.

Note: If you want to resize the existing attachment images for your resize models, run the 'Resize Attachment Image'
scheduled action. Each run will resize only 1,000 records to prevent prolonged processing times.
You will need to run the action multiple times until all your records are resized.
