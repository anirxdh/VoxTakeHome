export interface Provider {
  id: string;
  full_name: string;
  specialty: string;
  phone: string;
  email: string;
  address: {
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  years_experience: number;
  rating: number;
  board_certified: boolean;
  accepting_new_patients: boolean;
  languages: string[];
  insurance_accepted: string[];
  license_number: string;
}

