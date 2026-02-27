from pipeliner.jobs.relion.postprocess_job import PostprocessJob
from pipeliner.job_options import JobOptionValidationResult
from typing import Tuple, List

# Define Custom Postprocess Job to Avoid Future Warnings
class CustomPostprocessJob(PostprocessJob):                                                                             
      """
      Custom Post Processing Job to suppress the angpix requirement and auto sharpening validation
      """
      def __init__(self) -> None:
          super().__init__()
          self.joboptions["angpix"].is_required = False

      def validate_joboptions(self):
          angpix = self.joboptions["angpix"]
          was_blank = angpix.is_blank
          if was_blank:
              angpix._value = 1.0  # prevent crash in installed pipeliner's validate()
          results = super().validate_joboptions()
          if was_blank:
              angpix._value = None  # restore
              results = [r for r in results if angpix not in r.raised_by]
          return results

      def additional_joboption_validation(self) -> List[JobOptionValidationResult]:
          return []