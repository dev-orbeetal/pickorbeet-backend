import { useMemo } from 'react';
import {
  useGetDivisionsQuery,
  useGetDistrictsQuery,
  useGetPostOfficesQuery,
} from '@/store/api/geoApi';

/**
 * Cascading Division → District → Post office + free-text city for admin forms.
 * value: { division, district, post_office, postal_code, city }
 */
export default function BdAddressFields({ value, onChange, Field = 'div' }) {
  const division = value?.division || '';
  const district = value?.district || '';
  const postOffice = value?.post_office || '';
  const postalCode = value?.postal_code || '';
  const city = value?.city || '';

  const { data: divisions = [], isFetching: loadingDivisions } = useGetDivisionsQuery();
  const selectedDivision = useMemo(
    () => divisions.find((item) => item.name === division || item.slug === division),
    [divisions, division],
  );
  const divisionKey = selectedDivision?.slug || selectedDivision?.id || '';
  const { data: districts = [], isFetching: loadingDistricts } = useGetDistrictsQuery(divisionKey, {
    skip: !divisionKey,
  });
  const selectedDistrict = useMemo(
    () => districts.find((item) => item.name === district || item.slug === district),
    [districts, district],
  );
  const districtKey = selectedDistrict?.slug || selectedDistrict?.id || '';
  const { data: postOffices = [], isFetching: loadingOffices } = useGetPostOfficesQuery(districtKey, {
    skip: !districtKey,
  });

  const patch = (next) => onChange({ ...value, ...next });
  const Wrapper = Field;

  return (
    <>
      <Wrapper label="Division" required>
        <select
          className="input"
          required
          disabled={loadingDivisions}
          value={selectedDivision?.slug || ''}
          onChange={(event) => {
            const next = divisions.find((item) => item.slug === event.target.value);
            patch({
              division: next?.name || '',
              district: '',
              post_office: '',
              postal_code: '',
            });
          }}
        >
          <option value="">{loadingDivisions ? 'Loading…' : 'Select division'}</option>
          {divisions.map((item) => (
            <option key={item.id} value={item.slug}>{item.name}</option>
          ))}
        </select>
      </Wrapper>
      <Wrapper label="District" required>
        <select
          className="input"
          required
          disabled={!division || loadingDistricts}
          value={selectedDistrict?.slug || ''}
          onChange={(event) => {
            const next = districts.find((item) => item.slug === event.target.value);
            patch({
              district: next?.name || '',
              post_office: '',
              postal_code: '',
            });
          }}
        >
          <option value="">
            {!division ? 'Select division first' : loadingDistricts ? 'Loading…' : 'Select district'}
          </option>
          {districts.map((item) => (
            <option key={item.id} value={item.slug}>{item.name}</option>
          ))}
        </select>
      </Wrapper>
      <Wrapper label="Post office" required>
        <select
          className="input"
          required
          disabled={!district || loadingOffices}
          value={postOffice && postalCode ? `${postOffice}|||${postalCode}` : ''}
          onChange={(event) => {
            const [name, code] = event.target.value.split('|||');
            patch({ post_office: name || '', postal_code: code || '' });
          }}
        >
          <option value="">
            {!district ? 'Select district first' : loadingOffices ? 'Loading…' : 'Select post office'}
          </option>
          {postOffices.map((item) => (
            <option key={item.id} value={`${item.name}|||${item.postal_code}`}>
              {item.name} ({item.postal_code})
            </option>
          ))}
        </select>
      </Wrapper>
      <Wrapper label="City / locality" required>
        <input
          className="input"
          required
          value={city}
          placeholder="Area, locality, or neighbourhood"
          onChange={(event) => patch({ city: event.target.value })}
        />
      </Wrapper>
    </>
  );
}
