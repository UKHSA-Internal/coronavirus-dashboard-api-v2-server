#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from pathlib import Path
from os import getenv
from typing import NamedTuple, Dict, List, Callable, Any
from string import Template
from datetime import datetime
import re

# 3rd party:

# Internal: 

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'DBQueries',
    'DATA_TYPES',
    'ENVIRONMENT',
    'BASE_DIR'
]


ENVIRONMENT = getenv("ENVIRONMENT", "PRODUCTION")

BASE_DIR = Path(__file__).resolve().parent.parent


def to_template(text: str) -> Template:
    return Template(re.sub(r"[\n\t\s]+", " ", text, flags=re.MULTILINE).strip())


class DBQueries(NamedTuple):
    # noinspection SqlResolve,SqlNoDataSourceInspection
    main_data = to_template("""\
SELECT
    ar.area_type  AS "areaType",
    area_code     AS "areaCode",
    area_name     AS "areaName",
    date::VARCHAR AS date,
    metric,
    CASE
        WHEN (payload ? 'value') THEN (payload -> 'value')
        ELSE payload::JSONB
    END AS value
FROM covid19.time_series_p${partition} AS ts
    JOIN covid19.metric_reference  AS mr  ON mr.id = metric_id
    JOIN covid19.release_reference AS rr  ON rr.id = release_id
    JOIN covid19.area_reference    AS ar  ON ar.id = area_id
WHERE
      metric = ANY($$1::VARCHAR[])
  AND rr.released IS TRUE
  AND ar.area_type = $$2
  AND ts.area_id = ANY($$3::INT[])
  $filters
ORDER BY ts.date DESC""")

    nested_object = to_template("""\
SELECT
    ar.area_type                                                     AS "areaType",
    area_code                                                        AS "areaCode",
    area_name                                                        AS "areaName",
    date::VARCHAR                                                    AS date,
    mr.metric || UPPER(LEFT(ts_obj.key, 1)) || RIGHT(ts_obj.key, -1) AS metric,
    ts_obj.value                                                     AS value
FROM covid19.time_series_p${partition} AS ts
    JOIN covid19.metric_reference  AS mr  ON mr.id = metric_id
    JOIN covid19.area_reference    AS ar  ON ar.id = area_id
    JOIN covid19.release_reference AS rr  ON rr.id = release_id,
      JSONB_EACH(payload) AS ts_obj
WHERE
       mr.metric || UPPER(LEFT(ts_obj.key, 1)) || RIGHT(ts_obj.key, -1) = ANY($$1::VARCHAR[])
  AND rr.released IS TRUE
  AND ar.area_type = $$2
  AND ts.area_id = ANY($$3::INT[])
  $filters
ORDER BY ts.date DESC""")

    nested_object_with_area_code = to_template("""\
SELECT *
FROM
(
     SELECT area_type,
            area_code,
            area_name,
            date,
            metric || UPPER(LEFT(key, 1)) || RIGHT(key, -1) AS metric,
            value
     FROM covid19.time_series_p${partition} AS ts
         JOIN covid19.metric_reference  AS mr ON mr.id = metric_id
         JOIN covid19.release_reference AS rr ON rr.id = release_id
         JOIN covid19.area_reference    AS ar ON ar.id = area_id
         JOIN covid19.area_relation     AS arel ON arel.child_id = area_id,
           JSONB_EACH(payload)
     WHERE area_type = $$2
       AND metric || UPPER(LEFT(key, 1)) || RIGHT(key, -1) = ANY ($$1::VARCHAR[])
       AND rr.released IS TRUE
       AND parent_id = ANY ($$3::INT[])
     UNION
     (
          SELECT area_type,
                 area_code,
                 area_name,
                 date,
                 metric || UPPER(LEFT(key, 1)) || RIGHT(key, -1) AS metric,
                 value
          FROM covid19.time_series_p${partition} AS ts
              JOIN covid19.metric_reference  AS mr ON mr.id = metric_id
              JOIN covid19.release_reference AS rr ON rr.id = release_id
              JOIN covid19.area_reference    AS ar ON ar.id = area_id,
                JSONB_EACH(payload)
          WHERE area_type = $$2
            AND metric || UPPER(LEFT(key, 1)) || RIGHT(key, -1) = ANY($$1::VARCHAR[])
            AND rr.released IS TRUE
            AND area_id = ANY ($$3::INT[])
    )
) AS result
ORDER BY result.date DESC""")

    non_nested_object_with_area_code = to_template("""\
SELECT *
FROM
(
     SELECT area_type,
            area_code,
            area_name,
            date,
            metric,
            CASE
                WHEN (payload ? 'value') THEN (payload -> 'value')
                ELSE payload::JSONB
            END AS value
     FROM covid19.time_series_p${partition} AS ts
         JOIN covid19.metric_reference  AS mr ON mr.id = metric_id
         JOIN covid19.release_reference AS rr ON rr.id = release_id
         JOIN covid19.area_reference    AS ar ON ar.id = area_id
         JOIN covid19.area_relation     AS arel ON arel.child_id = area_id
     WHERE area_type = $$2
       AND metric = ANY ($$1::VARCHAR[])
       AND rr.released IS TRUE
       AND parent_id = ANY ($$3::INT[])
     UNION
     (
          SELECT area_type,
                 area_code,
                 area_name,
                 date,
                 metric,
                 CASE
                     WHEN (payload ? 'value') THEN (payload -> 'value')
                     ELSE payload::JSONB
                 END AS value
          FROM covid19.time_series_p${partition} AS ts
              JOIN covid19.metric_reference  AS mr ON mr.id = metric_id
              JOIN covid19.release_reference AS rr ON rr.id = release_id
              JOIN covid19.area_reference    AS ar ON ar.id = area_id
          WHERE area_type = $$2
            AND metric = ANY($$1::VARCHAR[])
            AND rr.released IS TRUE
            AND area_id = ANY ($$3::INT[])
    )
) AS result
ORDER BY result.date DESC""")

    nested_array = to_template("""\
SELECT
    ar.area_type  AS "areaType",
    area_code     AS "areaCode",
    area_name     AS "areaName",
    date::VARCHAR AS date,
    metric,
    payload       AS "${metric_name}"
FROM covid19.time_series_p${partition} AS ts
    JOIN covid19.metric_reference   AS mr  ON mr.id = metric_id
    JOIN covid19.release_reference  AS rr  ON rr.id = release_id
    JOIN covid19.area_reference    AS ar  ON ar.id = area_id
WHERE
      metric = ANY($$1::VARCHAR[])
  AND rr.released IS TRUE
  AND ar.area_type = $$2
  AND ts.area_id = ANY($$3::INT[])
  $filters
ORDER BY date DESC""")

    # noinspection SqlResolve,SqlNoDataSourceInspection
    exists = to_template("""\
SELECT
    area_code     AS "areaCode"
FROM covid19.time_series_p${partition} AS ts
    JOIN covid19.metric_reference  AS mr  ON mr.id = metric_id
    JOIN covid19.release_reference AS rr  ON rr.id = release_id
WHERE
      metric = ANY($$1::VARCHAR[])
  AND rr.released IS TRUE
  AND ar.area_type = $$2
  AND ts.area_id = ANY($$3::INT[])
  $filters
FETCH FIRST 1 ROW ONLY""")

    area_id_by_type = """\
SELECT MIN(id) AS id 
FROM covid19.area_reference 
WHERE area_type = $1 
GROUP BY area_code"""

    area_id_by_code_no_type = """\
SELECT MIN(id) AS id 
FROM covid19.area_reference 
WHERE area_code = $1 
GROUP BY area_code"""

    area_id_by_code = """\
SELECT MIN(id) AS id 
FROM covid19.area_reference 
WHERE area_code = $1 
  AND area_type = $2 
GROUP BY area_code"""


DATA_TYPES: Dict[str, Callable[[str], Any]] = {
    'hash': str,
    'areaType': str,
    'date': datetime,
    'areaName': str,
    'areaNameLower': str,
    'areaCode': str,
    'covidOccupiedMVBeds': int,
    'cumAdmissions': int,
    'cumCasesByPublishDate': int,
    'cumPillarFourTestsByPublishDate': int,
    'cumPillarOneTestsByPublishDate': int,
    'cumPillarThreeTestsByPublishDate': int,
    'cumPillarTwoTestsByPublishDate': int,
    'cumTestsByPublishDate': int,
    'hospitalCases': int,
    'newAdmissions': int,
    'newCasesByPublishDate': int,
    'newPillarFourTestsByPublishDate': int,
    'newPillarOneTestsByPublishDate': int,
    'newPillarThreeTestsByPublishDate': int,
    'newPillarTwoTestsByPublishDate': int,
    'newTestsByPublishDate': int,
    'plannedCapacityByPublishDate': int,
    'newCasesBySpecimenDate': int,
    'cumCasesBySpecimenDate': int,
    'maleCases': list,
    'femaleCases': list,
    'cumAdmissionsByAge': list,

    "femaleDeaths28Days": list,
    "maleDeaths28Days": list,

    'changeInNewCasesBySpecimenDate': int,
    'previouslyReportedNewCasesBySpecimenDate': int,

    "cumCasesBySpecimenDateRate": float,
    'cumCasesByPublishDateRate': float,

    'release': datetime,

    "newDeathsByDeathDate": int,
    "newDeathsByDeathDateRate": float,
    'newDeathsByDeathDateRollingRate': float,
    'newDeathsByDeathDateRollingSum': int,
    "cumDeathsByDeathDate": int,
    "cumDeathsByDeathDateRate": float,

    "newDeathsByPublishDate": int,
    "cumDeathsByPublishDate": int,
    "cumDeathsByPublishDateRate": float,

    "newDeaths28DaysByDeathDate": int,
    "newDeaths28DaysByDeathDateRate": float,
    'newDeaths28DaysByDeathDateRollingRate': float,
    'newDeaths28DaysByDeathDateRollingSum': int,
    "cumDeaths28DaysByDeathDate": int,
    "cumDeaths28DaysByDeathDateRate": float,

    "newDeaths28DaysByPublishDate": int,
    "cumDeaths28DaysByPublishDate": int,
    "cumDeaths28DaysByPublishDateRate": float,

    "newDeaths60DaysByDeathDate": int,
    "newDeaths60DaysByDeathDateRate": float,
    'newDeaths60DaysByDeathDateRollingRate': float,
    'newDeaths60DaysByDeathDateRollingSum': int,
    "cumDeaths60DaysByDeathDate": int,
    "cumDeaths60DaysByDeathDateRate": float,

    "newDeaths60DaysByPublishDate": int,
    "cumDeaths60DaysByPublishDate": int,
    "cumDeaths60DaysByPublishDateRate": float,

    'newOnsDeathsByRegistrationDate': int,
    'cumOnsDeathsByRegistrationDate': int,
    'cumOnsDeathsByRegistrationDateRate': float,

    "capacityPillarOneTwoFour": int,
    "newPillarOneTwoTestsByPublishDate": int,
    "capacityPillarOneTwo": int,
    "capacityPillarThree": int,
    "capacityPillarOne": int,
    "capacityPillarTwo": int,
    "capacityPillarFour": int,

    "cumPillarOneTwoTestsByPublishDate": int,

    "newPCRTestsByPublishDate": int,
    "cumPCRTestsByPublishDate": int,
    "plannedPCRCapacityByPublishDate": int,
    "plannedAntibodyCapacityByPublishDate": int,
    "newAntibodyTestsByPublishDate": int,
    "cumAntibodyTestsByPublishDate": int,

    "alertLevel": int,
    "transmissionRateMin": float,
    "transmissionRateMax": float,
    "transmissionRateGrowthRateMin": float,
    "transmissionRateGrowthRateMax": float,

    'newLFDTestsBySpecimenDate': int,
    'cumLFDTestsBySpecimenDate': int,
    'newVirusTestsByPublishDate': int,
    'cumVirusTestsByPublishDate': int,

    'newCasesBySpecimenDateDirection': str,
    'newCasesBySpecimenDateChange': int,
    'newCasesBySpecimenDateChangePercentage': float,
    'newCasesBySpecimenDateRollingSum': int,
    'newCasesBySpecimenDateRollingRate': float,
    'newCasesByPublishDateDirection': str,
    'newCasesByPublishDateChange': int,
    'newCasesByPublishDateChangePercentage': float,
    'newCasesByPublishDateRollingSum': int,
    'newCasesByPublishDateRollingRate': float,
    'newAdmissionsDirection': str,
    'newAdmissionsChange': int,
    'newAdmissionsChangePercentage': float,
    'newAdmissionsRollingSum': int,
    'newAdmissionsRollingRate': float,
    'newDeaths28DaysByPublishDateDirection': str,
    'newDeaths28DaysByPublishDateChange': int,
    'newDeaths28DaysByPublishDateChangePercentage': float,
    'newDeaths28DaysByPublishDateRollingSum': int,
    'newDeaths28DaysByPublishDateRollingRate': float,
    'newPCRTestsByPublishDateDirection': str,
    'newPCRTestsByPublishDateChange': int,
    'newPCRTestsByPublishDateChangePercentage': float,
    'newPCRTestsByPublishDateRollingSum': int,
    'newPCRTestsByPublishDateRollingRate': float,
    'newVirusTestsDirection': str,
    'newVirusTestsChange': int,
    'newVirusTestsChangePercentage': float,
    'newVirusTestsRollingSum': int,
    'newVirusTestsRollingRate': float,

    'newCasesByPublishDateAgeDemographics': list,
    'newCasesBySpecimenDateAgeDemographics': list,
    'newDeaths28DaysByDeathDateAgeDemographics': list,

    "uniqueCasePositivityBySpecimenDateRollingSum": float,
    "uniquePeopleTestedBySpecimenDateRollingSum": int,

    "newDailyNsoDeathsByDeathDate": int,
    "cumDailyNsoDeathsByDeathDate": int,

    "cumWeeklyNsoDeathsByRegDate": int,
    "cumWeeklyNsoDeathsByRegDateRate": float,
    "newWeeklyNsoDeathsByRegDate": int,
    "cumWeeklyNsoCareHomeDeathsByRegDate": int,
    "newWeeklyNsoCareHomeDeathsByRegDate": int,

    "newPeopleReceivingFirstDose": int,
    "cumPeopleReceivingFirstDose": int,
    "newPeopleReceivingSecondDose": int,
    "cumPeopleReceivingSecondDose": int,

    "cumPeopleVaccinatedFirstDoseByPublishDate": int,
    "cumPeopleVaccinatedSecondDoseByPublishDate": int,
    "newPeopleVaccinatedFirstDoseByPublishDate": int,
    "cumPeopleVaccinatedCompleteByPublishDate": int,
    "newPeopleVaccinatedCompleteByPublishDate": int,
    "newPeopleVaccinatedSecondDoseByPublishDate": int,
    "weeklyPeopleVaccinatedFirstDoseByVaccinationDate": int,
    "weeklyPeopleVaccinatedSecondDoseByVaccinationDate": int,
    "cumPeopleVaccinatedSecondDoseByVaccinationDate": int,
    'newCasesLFDConfirmedPCRBySpecimenDateRollingSum': int,
    'newCasesLFDConfirmedPCRBySpecimenDate': int,
    'newCasesLFDConfirmedPCRBySpecimenDateRollingRate': float,

    'cumCasesLFDOnlyBySpecimenDate': int,
    'cumCasesPCROnlyBySpecimenDate': int,
    'newCasesPCROnlyBySpecimenDateRollingSum': int,
    'newCasesLFDOnlyBySpecimenDateRollingRate': float,
    'newCasesPCROnlyBySpecimenDateRollingRate': float,
    'newCasesLFDOnlyBySpecimenDateRollingSum': int,
    'cumCasesLFDConfirmedPCRBySpecimenDate': int,
    'newCasesPCROnlyBySpecimenDate': int,
    'newCasesLFDOnlyBySpecimenDate': int,
    'newVaccinesGivenByPublishDate': int,
    'cumVaccinesGivenByPublishDate': int,

    "cumVaccinationFirstDoseUptakeByPublishDatePercentage": float,
    "cumVaccinationSecondDoseUptakeByPublishDatePercentage": float,
    "cumVaccinationCompleteCoverageByPublishDatePercentage": float,

    "newPeopleVaccinatedFirstDoseByVaccinationDate": int,
    "cumPeopleVaccinatedFirstDoseByVaccinationDate": int,
    "cumVaccinationSecondDoseUptakeByVaccinationDatePercentage": float,
    "VaccineRegisterPopulationByVaccinationDate": int,
    "newPeopleVaccinatedSecondDoseByVaccinationDate": int,
    "cumPeopleVaccinatedCompleteByVaccinationDate": int,
    "cumVaccinationFirstDoseUptakeByVaccinationDatePercentage": float,
    "cumVaccinationCompleteCoverageByVaccinationDatePercentage": float,
    "newPeopleVaccinatedCompleteByVaccinationDate": int,

    "vaccinationsAgeDemographics": list,

    "cumPeopleVaccinatedThirdDoseByPublishDate": int,
    "newPeopleVaccinatedThirdDoseByPublishDate": int,
    "cumVaccinationBoosterDoseUptakeByPublishDatePercentage": float,
    "cumPeopleVaccinatedThirdInjectionByPublishDate": int,
    "newPeopleVaccinatedThirdInjectionByPublishDate": int,
    "newPeopleVaccinatedBoosterDoseByPublishDate": int,
    "cumVaccinationThirdInjectionUptakeByPublishDatePercentage": float,
    "cumPeopleVaccinatedBoosterDoseByPublishDate": int,

    "cumPCRTestsBySpecimenDate": int,
    "newPCRTestsBySpecimenDate": int,
    "newVirusTestsBySpecimenDate": int,
    "cumVirusTestsBySpecimenDate": int,

    'cumPeopleVaccinatedThirdInjectionByVaccinationDate': int,
    'newPeopleVaccinatedThirdInjectionByVaccinationDate': int,
    'cumVaccinationThirdInjectionUptakeByVaccinationDatePercentage': float,
}


RESTRICTED_PARAMETER_VALUES: Dict[str, List[str]] = dict()


if ENVIRONMENT == "DEVELOPMENT":
    DATA_TYPES: Dict[str, Callable[[str], Any]] = {
        'hash': str,
        'areaType': str,
        'date': datetime,
        'areaName': str,
        'areaNameLower': str,
        'areaCode': str,
        'changeInCumCasesBySpecimenDate': int,
        'changeInNewCasesBySpecimenDate': int,
        'cumPeopleTestedBySpecimenDate': int,
        'covidOccupiedMVBeds': int,
        'covidOccupiedNIVBeds': int,
        'covidOccupiedOSBeds': int,
        'covidOccupiedOtherBeds': int,
        'cumAdmissions': int,
        'cumAdmissionsByAge': list,
        'cumCasesByPublishDate': int,
        'cumCasesBySpecimenDate': int,
        # 'cumDeathsByDeathDate': int,
        # 'cumDeathsByPublishDate': int,
        'cumDischarges': int,
        'cumDischargesByAge': list,
        'cumNegativesBySpecimenDate': int,
        'cumPeopleTestedByPublishDate': int,
        # 'cumPillarFourPeopleTestedByPublishDate': int,  # Currently excluded.
        'cumPillarFourTestsByPublishDate': int,
        'cumPillarOnePeopleTestedByPublishDate': int,
        'cumPillarOneTestsByPublishDate': int,
        'cumPillarThreeTestsByPublishDate': int,
        'cumPillarTwoPeopleTestedByPublishDate': int,
        'cumPillarTwoTestsByPublishDate': int,
        'cumTestsByPublishDate': int,
        'femaleCases': list,
        # 'femaleDeaths': list,
        'femaleNegatives': list,
        'hospitalCases': int,
        'maleCases': list,
        # 'maleDeaths': list,
        'maleNegatives': list,
        'malePeopleTested': list,
        'femalePeopleTested': list,
        'newAdmissions': int,
        'newAdmissionsByAge': list,
        'newCasesByPublishDate': int,
        'newCasesBySpecimenDate': int,
        'newDischarges': int,
        'newNegativesBySpecimenDate': int,
        'newPeopleTestedByPublishDate': int,
        # 'newPillarFourPeopleTestedByPublishDate': int,   # Currently excluded.
        'newPillarFourTestsByPublishDate': int,
        'newPillarOnePeopleTestedByPublishDate': int,
        'newPillarOneTestsByPublishDate': int,
        'newPillarThreeTestsByPublishDate': int,
        'newPillarTwoPeopleTestedByPublishDate': int,
        'newPillarTwoTestsByPublishDate': int,
        'newTestsByPublishDate': int,
        'nonCovidOccupiedMVBeds': int,
        'nonCovidOccupiedNIVBeds': int,
        'nonCovidOccupiedOSBeds': int,
        'nonCovidOccupiedOtherBeds': int,
        'plannedCapacityByPublishDate': int,
        'plannedPillarFourCapacityByPublishDate': int,
        'plannedPillarOneCapacityByPublishDate': int,
        'plannedPillarThreeCapacityByPublishDate': int,
        'plannedPillarTwoCapacityByPublishDate': int,
        'previouslyReportedCumCasesBySpecimenDate': int,
        'previouslyReportedNewCasesBySpecimenDate': int,
        'suspectedCovidOccupiedMVBeds': int,
        'suspectedCovidOccupiedNIVBeds': int,
        'suspectedCovidOccupiedOSBeds': int,
        'suspectedCovidOccupiedOtherBeds': int,
        'totalBeds': int,
        'totalMVBeds': int,
        'totalNIVBeds': int,
        'totalOSBeds': int,
        'totalOtherBeds': int,
        'unoccupiedMVBeds': int,
        'unoccupiedNIVBeds': int,
        'unoccupiedOSBeds': int,
        'unoccupiedOtherBeds': int,
        'release': datetime,
        'newPeopleTestedBySpecimenDate': int,

        "newDeathsByDeathDate": int,
        "newDeathsByDeathDateRate": float,
        'newDeathsByDeathDateRollingRate': float,
        "cumDeathsByDeathDate": int,
        "cumDeathsByDeathDateRate": float,

        "newDeathsByPublishDate": int,
        "cumDeathsByPublishDate": int,
        "cumDeathsByPublishDateRate": float,

        "newDeaths28DaysByDeathDate": int,
        "newDeaths28DaysByDeathDateRate": float,
        'newDeaths28DaysByDeathDateRollingRate': float,
        "cumDeaths28DaysByDeathDate": int,
        "cumDeaths28DaysByDeathDateRate": float,

        "newDeaths28DaysByPublishDate": int,
        "cumDeaths28DaysByPublishDate": int,
        "cumDeaths28DaysByPublishDateRate": float,

        "newDeaths60DaysByDeathDate": int,
        "newDeaths60DaysByDeathDateRate": float,
        'newDeaths60DaysByDeathDateRollingRate': float,
        "cumDeaths60DaysByDeathDate": int,
        "cumDeaths60DaysByDeathDateRate": float,

        "femaleDeaths28Days": list,
        "femaleDeaths60Days": list,
        "maleDeaths28Days": list,
        "maleDeaths60Days": list,

        "newDeaths60DaysByPublishDate": int,
        "cumDeaths60DaysByPublishDate": int,
        "cumDeaths60DaysByPublishDateRate": float,

        'newOnsDeathsByRegistrationDate': int,
        'cumOnsDeathsByRegistrationDate': int,
        'cumOnsDeathsByRegistrationDateRate': float,

        "cumCasesBySpecimenDateRate": float,
        "cumCasesByPublishDateRate": float,
        "cumPeopleTestedByPublishDateRate": float,
        "cumAdmissionsRate": float,
        "cumDischargesRate": float,

        "capacityPillarOneTwoFour": int,
        "newPillarOneTwoTestsByPublishDate": int,
        "capacityPillarOneTwo": int,
        "capacityPillarThree": int,
        "capacityPillarOne": int,
        "capacityPillarTwo": int,
        "capacityPillarFour": int,

        "newPillarOneTwoFourTestsByPublishDate": int,
        "newCasesBySpecimenDateRate": float,

        "cumPillarOneTwoTestsByPublishDate": int,

        "newPCRTestsByPublishDate": int,
        "cumPCRTestsByPublishDate": int,
        "plannedPCRCapacityByPublishDate": int,
        "plannedAntibodyCapacityByPublishDate": int,
        "newAntibodyTestsByPublishDate": int,
        "cumAntibodyTestsByPublishDate": int,

        "newDeathsByDeathDateRollingSum": int,
        "newDeaths28DaysByDeathDateRollingSum": int,
        "newDeaths60DaysByDeathDateRollingSum": int,

        'newLFDTestsBySpecimenDate': int,
        'cumLFDTestsBySpecimenDate': int,
        'newVirusTestsByPublishDate': int,
        'cumVirusTestsByPublishDate': int,

        "alertLevel": int,
        "transmissionRateMin": float,
        "transmissionRateMax": float,
        "transmissionRateGrowthRateMin": float,
        "transmissionRateGrowthRateMax": float,

        'newCasesBySpecimenDateDirection': str,
        'newCasesBySpecimenDateChange': int,
        'newCasesBySpecimenDateChangePercentage': float,
        'newCasesBySpecimenDateRollingSum': int,
        'newCasesBySpecimenDateRollingRate': float,
        'newCasesByPublishDateDirection': str,
        'newCasesByPublishDateChange': int,
        'newCasesByPublishDateChangePercentage': float,
        'newCasesByPublishDateRollingSum': int,
        'newCasesByPublishDateRollingRate': float,
        'newAdmissionsDirection': str,
        'newAdmissionsChange': int,
        'newAdmissionsChangePercentage': float,
        'newAdmissionsRollingSum': int,
        'newAdmissionsRollingRate': float,
        'newDeaths28DaysByPublishDateDirection': str,
        'newDeaths28DaysByPublishDateChange': int,
        'newDeaths28DaysByPublishDateChangePercentage': float,
        'newDeaths28DaysByPublishDateRollingSum': int,
        'newDeaths28DaysByPublishDateRollingRate': float,
        'newPCRTestsByPublishDateDirection': str,
        'newPCRTestsByPublishDateChange': int,
        'newPCRTestsByPublishDateChangePercentage': float,
        'newPCRTestsByPublishDateRollingSum': int,
        'newPCRTestsByPublishDateRollingRate': float,
        'newVirusTestsDirection': str,
        'newVirusTestsChange': int,
        'newVirusTestsChangePercentage': float,
        'newVirusTestsRollingSum': int,
        'newVirusTestsRollingRate': float,

        "newOnsCareHomeDeathsByRegistrationDate": int,
        "cumOnsCareHomeDeathsByRegistrationDate": int,

        'newCasesByPublishDateAgeDemographics': list,
        'newCasesBySpecimenDateAgeDemographics': list,
        'newDeaths28DaysByDeathDateAgeDemographics': list,

        "uniqueCasePositivityBySpecimenDateRollingSum": float,
        "uniquePeopleTestedBySpecimenDateRollingSum": int,

        "newPeopleReceivingFirstDose": int,
        "cumPeopleReceivingFirstDose": int,
        "newPeopleReceivingSecondDose": int,
        "cumPeopleReceivingSecondDose": int,

        "cumWeeklyNsoDeathsByRegDate": int,
        "cumWeeklyNsoDeathsByRegDateRate": float,
        "newWeeklyNsoDeathsByRegDate": int,
        "cumWeeklyNsoCareHomeDeathsByRegDate": int,
        "newWeeklyNsoCareHomeDeathsByRegDate": int,

        "newDailyNsoDeathsByDeathDate": int,
        "cumDailyNsoDeathsByDeathDate": int,

        "cumPeopleVaccinatedFirstDoseByPublishDate": int,
        "cumPeopleVaccinatedSecondDoseByPublishDate": int,
        "newPeopleVaccinatedFirstDoseByPublishDate": int,
        "cumPeopleVaccinatedCompleteByPublishDate": int,
        "newPeopleVaccinatedCompleteByPublishDate": int,
        "newPeopleVaccinatedSecondDoseByPublishDate": int,
        "weeklyPeopleVaccinatedFirstDoseByVaccinationDate": int,
        "weeklyPeopleVaccinatedSecondDoseByVaccinationDate": int,
        "cumPeopleVaccinatedSecondDoseByVaccinationDate": int,

        'newCasesPCROnlyBySpecimenDateRollingSum': int,
        'newCasesLFDOnlyBySpecimenDateRollingRate': float,
        'newCasesLFDOnlyBySpecimenDate': int,
        'cumCasesPCROnlyBySpecimenDate': int,
        'newCasesPCROnlyBySpecimenDateRollingRate': float,
        'newCasesLFDOnlyBySpecimenDateRollingSum': int,
        'cumCasesLFDConfirmedPCRBySpecimenDate': int,
        'cumCasesLFDOnlyBySpecimenDate': int,
        'newCasesPCROnlyBySpecimenDate': int,
        'newCasesLFDConfirmedPCRBySpecimenDateRollingSum': int,
        'newCasesLFDConfirmedPCRBySpecimenDate': int,
        'newCasesLFDConfirmedPCRBySpecimenDateRollingRate': float,

        "cumVaccinationFirstDoseUptakeByPublishDatePercentage": float,
        "cumVaccinationSecondDoseUptakeByPublishDatePercentage": float,
        "cumVaccinationCompleteCoverageByPublishDatePercentage": float,

        "newPeopleVaccinatedFirstDoseByVaccinationDate": int,
        "cumPeopleVaccinatedFirstDoseByVaccinationDate": int,
        "cumVaccinationSecondDoseUptakeByVaccinationDatePercentage": float,
        "VaccineRegisterPopulationByVaccinationDate": int,
        "newPeopleVaccinatedSecondDoseByVaccinationDate": int,
        "cumPeopleVaccinatedCompleteByVaccinationDate": int,
        "cumVaccinationFirstDoseUptakeByVaccinationDatePercentage": float,
        "cumVaccinationCompleteCoverageByVaccinationDatePercentage": float,
        "newPeopleVaccinatedCompleteByVaccinationDate": int,

        "vaccinationsAgeDemographics": list,

        "cumPeopleVaccinatedThirdDoseByPublishDate": int,
        "newPeopleVaccinatedThirdDoseByPublishDate": int,
        "cumVaccinationBoosterDoseUptakeByPublishDatePercentage": float,
        "cumPeopleVaccinatedThirdInjectionByPublishDate": int,
        "newPeopleVaccinatedThirdInjectionByPublishDate": int,
        "newPeopleVaccinatedBoosterDoseByPublishDate": int,
        "cumVaccinationThirdInjectionUptakeByPublishDatePercentage": float,
        "cumPeopleVaccinatedBoosterDoseByPublishDate": int,

        "cumPCRTestsBySpecimenDate": int,
        "newPCRTestsBySpecimenDate": int,
        "newVirusTestsBySpecimenDate": int,
        "cumVirusTestsBySpecimenDate": int,

        'cumPeopleVaccinatedThirdInjectionByVaccinationDate': int,
        'newPeopleVaccinatedThirdInjectionByVaccinationDate': int,
        'cumVaccinationThirdInjectionUptakeByVaccinationDatePercentage': float,
    }
